#!/usr/bin/env python3
"""
后端集成示例

演示如何在FastAPI后端中集成Baseline服务，包括API端点设计和数据流转。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import json

# ====== 数据模型定义 ======

class HealthKitSleepRecord(BaseModel):
    """HealthKit睡眠记录"""
    date: str  # ISO格式: "2024-01-01T00:00:00Z" 
    sleep_duration_hours: float
    sleep_efficiency: float
    deep_sleep_minutes: Optional[int] = None
    rem_sleep_minutes: Optional[int] = None 
    total_sleep_minutes: Optional[int] = None
    restorative_ratio: Optional[float] = None

class HealthKitHRVRecord(BaseModel):
    """HealthKit HRV记录"""
    timestamp: str  # ISO格式: "2024-01-01T08:00:00Z"
    sdnn_value: float  # SDNN值，单位ms

class BaselineCalculationRequest(BaseModel):
    """基线计算请求"""
    user_id: str
    sleep_records: List[HealthKitSleepRecord]
    hrv_records: List[HealthKitHRVRecord]
    force_recalculate: bool = False

class BaselineData(BaseModel):
    """基线数据"""
    sleep_baseline_hours: Optional[float] = None
    sleep_baseline_eff: Optional[float] = None
    rest_baseline_ratio: Optional[float] = None
    hrv_baseline_mu: Optional[float] = None
    hrv_baseline_sd: Optional[float] = None
    hrv_rmssd_28day_avg: Optional[float] = None
    hrv_rmssd_28day_sd: Optional[float] = None

class QualityMetrics(BaseModel):
    """数据质量指标"""
    data_quality_score: float
    sample_days_sleep: int
    sample_days_hrv: int
    completeness_sleep: float
    completeness_hrv: float

class BaselineResult(BaseModel):
    """基线计算结果"""
    user_id: str
    baseline_data: BaselineData
    quality_metrics: QualityMetrics
    calculated_at: str
    expires_at: str
    algorithm_version: str = "1.0.0"

class ReadinessCalculationRequest(BaseModel):
    """准备度计算请求"""
    user_id: str
    
    # 当天数据
    sleep_duration_hours: float
    sleep_efficiency: float
    hrv_rmssd_today: Optional[float] = None
    restorative_ratio: Optional[float] = None
    
    # Hooper量表
    fatigue_hooper: Optional[int] = None
    stress_hooper: Optional[int] = None
    
    # 布尔日志
    is_sick: bool = False
    is_injured: bool = False

# ====== API端点实现 ======

class BaselineAPI:
    """Baseline服务API实现示例"""
    
    def __init__(self):
        self.baseline_storage = {}  # 模拟数据库存储
        
    async def calculate_baseline(self, request: BaselineCalculationRequest) -> BaselineResult:
        """计算用户个人基线
        
        POST /api/v1/baseline/calculate
        """
        user_id = request.user_id
        
        # 1. 检查是否需要重新计算
        if not request.force_recalculate:
            existing = self.baseline_storage.get(user_id)
            if existing and not self._is_baseline_expired(existing):
                return existing
        
        # 2. 数据验证和预处理
        sleep_records = self._validate_sleep_records(request.sleep_records)
        hrv_records = self._validate_hrv_records(request.hrv_records)
        
        if len(sleep_records) < 15:
            raise ValueError(f"睡眠数据不足，需要至少15天记录，当前{len(sleep_records)}天")
        
        if len(hrv_records) < 10:
            raise ValueError(f"HRV数据不足，需要至少10个记录，当前{len(hrv_records)}个")
        
        # 3. 基线计算 (调用baseline模块)
        from baseline import PersonalBaselineCalculator
        from baseline.models import SleepRecord, HRVRecord
        
        calculator = PersonalBaselineCalculator()
        
        # 转换数据格式
        sleep_data = [
            SleepRecord(
                date=datetime.fromisoformat(r.date.replace('Z', '+00:00')),
                sleep_duration_hours=r.sleep_duration_hours,
                sleep_efficiency=r.sleep_efficiency,
                restorative_ratio=r.restorative_ratio
            )
            for r in sleep_records
        ]
        
        hrv_data = [
            HRVRecord(
                timestamp=datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')),
                sdnn_value=r.sdnn_value
            )
            for r in hrv_records
        ]
        
        # 执行计算
        baseline_result = calculator.calculate_baseline(user_id, sleep_data, hrv_data)
        
        # 4. 格式化返回结果
        now = datetime.now()
        expires_at = now + timedelta(days=7)  # 7天后过期
        
        result = BaselineResult(
            user_id=user_id,
            baseline_data=BaselineData(
                sleep_baseline_hours=baseline_result.sleep_baseline_hours,
                sleep_baseline_eff=baseline_result.sleep_baseline_eff,
                rest_baseline_ratio=baseline_result.rest_baseline_ratio,
                hrv_baseline_mu=baseline_result.hrv_baseline_mu,
                hrv_baseline_sd=baseline_result.hrv_baseline_sd
            ),
            quality_metrics=QualityMetrics(
                data_quality_score=baseline_result.data_quality_score,
                sample_days_sleep=baseline_result.sample_days_sleep,
                sample_days_hrv=baseline_result.sample_days_hrv,
                completeness_sleep=0.9,  # 示例值
                completeness_hrv=0.85
            ),
            calculated_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )
        
        # 5. 保存到存储
        self.baseline_storage[user_id] = result
        
        return result
    
    async def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        """获取用户基线数据
        
        GET /api/v1/baseline/{user_id}
        """
        baseline = self.baseline_storage.get(user_id)
        
        if baseline and self._is_baseline_expired(baseline):
            return None  # 已过期
            
        return baseline
    
    def _validate_sleep_records(self, records: List[HealthKitSleepRecord]) -> List[HealthKitSleepRecord]:
        """验证睡眠数据"""
        valid_records = []
        
        for record in records:
            # 基本验证
            if 2.0 <= record.sleep_duration_hours <= 12.0:
                if 0.3 <= record.sleep_efficiency <= 1.0:
                    valid_records.append(record)
        
        return valid_records
    
    def _validate_hrv_records(self, records: List[HealthKitHRVRecord]) -> List[HealthKitHRVRecord]:
        """验证HRV数据"""
        valid_records = []
        
        for record in records:
            # HRV SDNN通常在10-100ms范围
            if 10.0 <= record.sdnn_value <= 100.0:
                valid_records.append(record)
        
        return valid_records
    
    def _is_baseline_expired(self, baseline: BaselineResult) -> bool:
        """检查基线是否已过期"""
        expires_at = datetime.fromisoformat(baseline.expires_at)
        return datetime.now() > expires_at

class ReadinessAPI:
    """准备度计算API实现示例"""
    
    def __init__(self, baseline_api: BaselineAPI):
        self.baseline_api = baseline_api
    
    async def calculate_readiness(self, request: ReadinessCalculationRequest) -> Dict[str, Any]:
        """计算准备度评分
        
        POST /api/v1/readiness/calculate
        """
        user_id = request.user_id
        
        # 1. 获取用户基线数据
        baseline = await self.baseline_api.get_baseline(user_id)
        
        if not baseline:
            raise ValueError(f"用户{user_id}基线数据不存在或已过期，请先计算基线")
        
        # 2. 构造mapping.py需要的payload格式
        payload = {
            # 当天数据
            "sleep_duration_hours": request.sleep_duration_hours,
            "sleep_efficiency": request.sleep_efficiency,
            "hrv_rmssd_today": request.hrv_rmssd_today,
            "restorative_ratio": request.restorative_ratio,
            
            # 个人基线数据
            "sleep_baseline_hours": baseline.baseline_data.sleep_baseline_hours,
            "sleep_baseline_eff": baseline.baseline_data.sleep_baseline_eff,
            "rest_baseline_ratio": baseline.baseline_data.rest_baseline_ratio,
            "hrv_baseline_mu": baseline.baseline_data.hrv_baseline_mu,
            "hrv_baseline_sd": baseline.baseline_data.hrv_baseline_sd,
            
            # Hooper量表
            "fatigue_hooper": request.fatigue_hooper,
            "stress_hooper": request.stress_hooper,
            
            # 布尔标记
            "is_sick": request.is_sick,
            "is_injured": request.is_injured,
        }
        
        # 3. 调用readiness模块计算
        from readiness.mapping import map_inputs_to_states
        
        mapped_states = map_inputs_to_states(payload)
        
        # 4. 根据mapped_states计算最终评分
        # 这里是示例逻辑，实际应该调用你的readiness计算引擎
        factors = {
            "sleep_performance": mapped_states.get("sleep_performance", "unknown"),
            "restorative_sleep": mapped_states.get("restorative_sleep", "unknown"), 
            "hrv_trend": mapped_states.get("hrv_trend", "unknown"),
            "subjective_fatigue": mapped_states.get("subjective_fatigue", "unknown"),
            "subjective_stress": mapped_states.get("subjective_stress", "unknown")
        }
        
        # 简单评分逻辑 (实际应该更复杂)
        score = self._calculate_readiness_score(factors)
        level = self._get_readiness_level(score)
        recommendations = self._generate_recommendations(factors, baseline.baseline_data)
        
        return {
            "user_id": user_id,
            "readiness_score": score,
            "readiness_level": level,
            "factors": factors,
            "recommendations": recommendations,
            "baseline_used": {
                "sleep_baseline_hours": baseline.baseline_data.sleep_baseline_hours,
                "data_quality_score": baseline.quality_metrics.data_quality_score
            },
            "calculated_at": datetime.now().isoformat()
        }
    
    def _calculate_readiness_score(self, factors: Dict[str, str]) -> int:
        """计算准备度评分 (0-100)"""
        score_map = {"good": 85, "high": 85, "medium": 65, "stable": 75, 
                    "poor": 45, "low": 45, "slight_decline": 55, 
                    "significant_decline": 35, "rising": 90}
        
        scores = [score_map.get(value, 65) for value in factors.values() if value != "unknown"]
        
        if not scores:
            return 65  # 默认分数
        
        return int(sum(scores) / len(scores))
    
    def _get_readiness_level(self, score: int) -> str:
        """获取准备度等级"""
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, factors: Dict[str, str], baseline: BaselineData) -> List[str]:
        """生成个性化建议"""
        recommendations = []
        
        if factors.get("sleep_performance") == "poor":
            if baseline.sleep_baseline_hours:
                recommendations.append(f"今晚试着早睡，达到你的个人基线{baseline.sleep_baseline_hours:.1f}小时")
            else:
                recommendations.append("增加睡眠时长，建议7-8小时")
        
        if factors.get("hrv_trend") in ["slight_decline", "significant_decline"]:
            recommendations.append("HRV下降，建议减少训练强度，增加恢复时间")
        
        if factors.get("subjective_stress") == "high":
            recommendations.append("压力较高，尝试冥想或深呼吸练习")
        
        return recommendations

# ====== 使用示例 ======

async def demonstrate_api_flow():
    """演示完整API流程"""
    
    print("🚀 后端API集成演示")
    print("=" * 50)
    
    # 初始化API服务
    baseline_api = BaselineAPI()
    readiness_api = ReadinessAPI(baseline_api)
    
    # 1. 模拟HealthKit数据上传
    print("\n1️⃣ 用户上传HealthKit数据")
    print("-" * 30)
    
    healthkit_request = BaselineCalculationRequest(
        user_id="user_123",
        sleep_records=[
            HealthKitSleepRecord(
                date="2024-01-01T00:00:00Z",
                sleep_duration_hours=7.5,
                sleep_efficiency=0.88,
                restorative_ratio=0.35
            ),
            # ... 更多记录
        ] * 20,  # 模拟20天数据
        hrv_records=[
            HealthKitHRVRecord(
                timestamp="2024-01-01T08:00:00Z",
                sdnn_value=42.3
            )
        ] * 15  # 模拟15个HRV记录
    )
    
    print(f"📱 接收到用户{healthkit_request.user_id}的HealthKit数据")
    print(f"📊 睡眠记录: {len(healthkit_request.sleep_records)}天")
    print(f"💓 HRV记录: {len(healthkit_request.hrv_records)}个")
    
    # 2. 计算基线
    print("\n2️⃣ 计算个人基线")
    print("-" * 30)
    
    try:
        baseline_result = await baseline_api.calculate_baseline(healthkit_request)
        print(f"✅ 基线计算成功")
        print(f"📏 睡眠基线: {baseline_result.baseline_data.sleep_baseline_hours:.1f}小时")
        print(f"💓 HRV基线: {baseline_result.baseline_data.hrv_baseline_mu:.1f}ms")
        print(f"📊 数据质量: {baseline_result.quality_metrics.data_quality_score:.2f}")
        
    except ValueError as e:
        print(f"❌ 基线计算失败: {e}")
        return
    
    # 3. 当天数据计算准备度
    print("\n3️⃣ 计算当天准备度")
    print("-" * 30)
    
    readiness_request = ReadinessCalculationRequest(
        user_id="user_123",
        sleep_duration_hours=6.8,  # 略低于基线
        sleep_efficiency=0.82,
        hrv_rmssd_today=35.0,      # 低于基线
        restorative_ratio=0.38,    # 高于基线
        fatigue_hooper=3,
        stress_hooper=4,
        is_sick=False,
        is_injured=False
    )
    
    print(f"🌙 当天睡眠: {readiness_request.sleep_duration_hours}h")
    print(f"💓 当天HRV: {readiness_request.hrv_rmssd_today}ms") 
    print(f"😴 恢复性睡眠: {readiness_request.restorative_ratio*100:.0f}%")
    
    readiness_result = await readiness_api.calculate_readiness(readiness_request)
    
    print(f"\n🎯 准备度结果:")
    print(f"   评分: {readiness_result['readiness_score']}/100 ({readiness_result['readiness_level']})")
    print(f"   睡眠表现: {readiness_result['factors']['sleep_performance']}")
    print(f"   HRV趋势: {readiness_result['factors']['hrv_trend']}")
    print(f"   恢复性睡眠: {readiness_result['factors']['restorative_sleep']}")
    
    print(f"\n💡 个性化建议:")
    for recommendation in readiness_result['recommendations']:
        print(f"   • {recommendation}")

def get_fastapi_example():
    """FastAPI集成示例代码"""
    
    fastapi_code = '''
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI(title="Readiness API")

# 初始化服务
baseline_api = BaselineAPI()
readiness_api = ReadinessAPI(baseline_api)

@app.post("/api/v1/baseline/calculate", response_model=BaselineResult)
async def calculate_baseline(request: BaselineCalculationRequest):
    """计算用户个人基线"""
    try:
        result = await baseline_api.calculate_baseline(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/baseline/{user_id}", response_model=BaselineResult)
async def get_baseline(user_id: str):
    """获取用户基线数据"""
    baseline = await baseline_api.get_baseline(user_id)
    if not baseline:
        raise HTTPException(status_code=404, detail="基线数据不存在或已过期")
    return baseline

@app.post("/api/v1/readiness/calculate")
async def calculate_readiness(request: ReadinessCalculationRequest) -> Dict[str, Any]:
    """计算准备度评分"""
    try:
        result = await readiness_api.calculate_readiness(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# 数据库集成示例
from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserBaseline(Base):
    __tablename__ = "user_baselines"
    
    user_id = Column(String, primary_key=True)
    sleep_baseline_hours = Column(Float)
    sleep_baseline_eff = Column(Float)  
    rest_baseline_ratio = Column(Float)
    hrv_baseline_mu = Column(Float)
    hrv_baseline_sd = Column(Float)
    data_quality_score = Column(Float)
    calculated_at = Column(DateTime)
    expires_at = Column(DateTime)
    metadata_json = Column(Text)  # 存储额外元数据
'''
    
    return fastapi_code

if __name__ == '__main__':
    import asyncio
    
    # 运行API流程演示
    asyncio.run(demonstrate_api_flow())
    
    # 输出FastAPI代码示例
    print(f"\n📄 FastAPI集成代码示例:")
    print("=" * 50)
    print(get_fastapi_example())