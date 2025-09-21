# Motivue API 开发文档 v0.1 (2025-09-21)

## 1. 核心功能变更：引入“可消耗的准备度”

为了支持用户训练后的准备度动态变化，本次更新引入了新的状态管理机制。现在，每个用户每天将有两个准备度分数：

-   **`final_readiness_score` (每日初始准备度)**:
    -   **含义**: 用户当天睡醒后，通过 `from-healthkit` 接口计算出的最原始、最核心的准备度分数。
    -   **用途**: 作为当天准备度的“最大值”和历史记录，一天内不再变化。
-   **`current_readiness_score` (当前剩余准备度)**:
    -   **含义**: 用户当前**实时**的、可用于消耗的准备度。
    -   **用途**: 初始值等于 `final_readiness_score`。每当用户记录一次训练消耗，该值就会降低。前端应始终以这个值为准来展示用户当前的准备度。

---

## 2. API 接口更新

### 2.1 `POST /readiness/from-healthkit` (每日准备度计算)

此接口的功能保持不变，依然是用于计算用户每日的初始准备度。

-   **核心变化**: 调用成功后，后端会自动将计算出的准备度分数同时写入 `final_readiness_score` 和 `current_readiness_score` 两个字段，为当天的消耗做好准备。
-   **调用时机**: 建议在用户App启动或进入主页时，检查当天是否已有准备度分数，若无则调用此接口。

#### 请求示例

```json
{
  "user_id": "u_test_full",
  "date": "2025-09-21",
  "gender": "男性",
  "ios_version": 25,
  "apple_sleep_score": null,
  "total_sleep_minutes": 495,
  "sleep_efficiency": 91,
  "restorative_ratio": 0.39,
  "hrv_rmssd_today": 58,
  "previous_state_probs": {
    "Peak": 0.1,
    "Well-adapted": 0.5,
    "FOR": 0.3,
    "Acute Fatigue": 0.1,
    "NFOR": 0,
    "OTS": 0
  }
}
```

#### 响应示例

```json
{
  "user_id": "u_test_full",
  "date": "2025-09-21",
  "final_readiness_score": 85,
  "final_diagnosis": "适应良好",
  // ... 其他字段
}
```

### 2.2 `POST /readiness/consumption` (**新增**: 训练消耗计算)

这是本次新增的核心接口，用于计算并记录用户训练后的准备度消耗。

-   **功能**:
    1.  接收用户单次或多次训练的 `RPE` (自觉运动强度, 1-10) 和 `duration_minutes` (持续时间，分钟)。
    2.  从数据库读取**当前剩余准备度** (`current_readiness_score`) 作为计算基础。
    3.  计算消耗分数，得出一个新的**“展示用准备度”** (`display_readiness`)。
    4.  将这个 `display_readiness` 写回到数据库的 `current_readiness_score` 字段，完成状态的持久化更新。
-   **调用时机**: 当用户完成一次训练并输入 RPE 和时长后调用。

#### 请求体

| 字段 | 类型 | 必选 | 描述 |
| :--- | :--- | :--- | :--- |
| `user_id` | string | 是 | 用户唯一标识符。 |
| `date` | string | 是 | 训练发生的日期 (格式: "YYYY-MM-DD")。 |
| `sessions` | array | 是 | 训练记录数组，可包含一或多条记录。 |
| `sessions[].rpe`| integer | 是 | 自觉运动强度, 范围 `1` 到 `10`。 |
| `sessions[].duration_minutes` | integer | 是 | 训练持续分钟数, 范围 `1` 以上。 |
| `sessions[].label` | string | 否 | 训练标签，如 "上午跑步"。 |

#### 请求示例

```json
{
  "user_id": "u_test_full",
  "date": "2025-09-21",
  "sessions": [
    {
      "rpe": 7,
      "duration_minutes": 60,
      "label": "高强度间歇"
    }
  ]
}
```

#### 响应体

| 字段 | 类型 | 描述 |
| :--- | :--- | :--- |
| `user_id` | string | 用户ID。 |
| `date` | string | 日期。 |
| `base_readiness_score` | integer | 本次计算时所基于的准备度分数 (即消耗前的 `current_readiness_score`)。 |
| `consumption_score` | float | 计算出的总消耗分数。 |
| `display_readiness` | integer | **前端应展示给用户的最新准备度分数**。 |
| `breakdown` | object | 消耗明细。 |
| `sessions` | array | 每条 session 的详细计算结果。 |

#### 响应示例

```json
{
  "user_id": "u_test_full",
  "date": "2025-09-21",
  "base_readiness_score": 85,
  "consumption_score": 15.0,
  "display_readiness": 70,
  "breakdown": {
    "training": 15.0
  },
  "sessions": [
    // ...
  ]
}
```

---

## 3. 前端调用流程建议

1.  **每日首次加载**:
    -   检查用户当天 (`YYYY-MM-DD`) 是否已有准备度分数。
    -   若无，调用 `POST /readiness/from-healthkit` 获取初始分数。
    -   将返回的 `final_readiness_score` 作为今日的初始值和当前值进行展示。

2.  **用户记录训练**:
    -   用户在前端界面输入 RPE 和时长。
    -   App 调用 `POST /readiness/consumption` 接口。
    -   **关键**: 使用接口返回的 `display_readiness` 值，**更新并覆盖**前端当前显示的准备度分数。

3.  **后续操作**:
    -   如果用户当天再次进行训练，重复**步骤 2**。后端会自动基于上一次消耗后的 `current_readiness_score` 进行计算，确保准备度被连续消耗。
    -   只要是当天，无论用户如何刷新或重开 App，都应展示 `current_readiness_score` 的最新值（可以通过在主页再次请求一个 `GET /user/{user_id}/daily/{date}` 的接口来获取，如果需要的话）。
    -   第二天，流程回到**步骤 1**，`from-healthkit` 会重新初始化新一天的准备度分数。
