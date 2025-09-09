"""基线数据存储管理

提供基线数据的存储、检索和管理功能。
支持多种存储后端：内存、文件、数据库等。
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3

from .models import BaselineResult


class BaselineStorage:
    """基线存储的抽象基类"""
    
    def save_baseline(self, baseline: BaselineResult) -> bool:
        """保存基线数据"""
        raise NotImplementedError
    
    def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        """获取基线数据"""
        raise NotImplementedError
    
    def delete_baseline(self, user_id: str) -> bool:
        """删除基线数据"""
        raise NotImplementedError
    
    def list_users_with_baselines(self) -> List[str]:
        """列出所有有基线数据的用户"""
        raise NotImplementedError
    
    def get_outdated_baselines(self, days_threshold: int = 7) -> List[str]:
        """获取过期的基线数据用户列表"""
        raise NotImplementedError


class MemoryBaselineStorage(BaselineStorage):
    """内存存储实现（用于测试和开发）"""
    
    def __init__(self):
        self._storage: Dict[str, BaselineResult] = {}
    
    def save_baseline(self, baseline: BaselineResult) -> bool:
        try:
            self._storage[baseline.user_id] = baseline
            return True
        except Exception:
            return False
    
    def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        return self._storage.get(user_id)
    
    def delete_baseline(self, user_id: str) -> bool:
        try:
            if user_id in self._storage:
                del self._storage[user_id]
            return True
        except Exception:
            return False
    
    def list_users_with_baselines(self) -> List[str]:
        return list(self._storage.keys())
    
    def get_outdated_baselines(self, days_threshold: int = 7) -> List[str]:
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        return [
            user_id for user_id, baseline in self._storage.items()
            if baseline.created_at and baseline.created_at < threshold_date
        ]


class FileBaselineStorage(BaselineStorage):
    """文件存储实现"""
    
    def __init__(self, storage_dir: str = "baseline_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
    
    def _get_file_path(self, user_id: str) -> Path:
        """获取用户基线数据文件路径"""
        return self.storage_dir / f"{user_id}_baseline.json"
    
    def save_baseline(self, baseline: BaselineResult) -> bool:
        try:
            file_path = self._get_file_path(baseline.user_id)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(baseline.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存基线数据到文件失败: {e}")
            return False
    
    def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        try:
            file_path = self._get_file_path(user_id)
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return BaselineResult.from_dict(data)
                
        except Exception as e:
            print(f"从文件读取基线数据失败: {e}")
            return None
    
    def delete_baseline(self, user_id: str) -> bool:
        try:
            file_path = self._get_file_path(user_id)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"删除基线数据文件失败: {e}")
            return False
    
    def list_users_with_baselines(self) -> List[str]:
        try:
            baseline_files = list(self.storage_dir.glob("*_baseline.json"))
            return [f.stem.replace('_baseline', '') for f in baseline_files]
        except Exception:
            return []
    
    def get_outdated_baselines(self, days_threshold: int = 7) -> List[str]:
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        outdated_users = []
        
        for user_id in self.list_users_with_baselines():
            baseline = self.get_baseline(user_id)
            if (baseline and baseline.created_at and 
                baseline.created_at < threshold_date):
                outdated_users.append(user_id)
        
        return outdated_users


class SQLiteBaselineStorage(BaselineStorage):
    """SQLite数据库存储实现"""
    
    def __init__(self, db_path: str = "baseline.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_baselines (
                    user_id TEXT PRIMARY KEY,
                    sleep_baseline_hours REAL,
                    sleep_baseline_eff REAL,
                    rest_baseline_ratio REAL,
                    hrv_baseline_mu REAL,
                    hrv_baseline_sd REAL,
                    data_quality_score REAL,
                    sample_days_sleep INTEGER,
                    sample_days_hrv INTEGER,
                    calculation_version TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
    
    def save_baseline(self, baseline: BaselineResult) -> bool:
        try:
            now = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_baselines 
                    (user_id, sleep_baseline_hours, sleep_baseline_eff, rest_baseline_ratio,
                     hrv_baseline_mu, hrv_baseline_sd, data_quality_score, 
                     sample_days_sleep, sample_days_hrv, calculation_version,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    baseline.user_id,
                    baseline.sleep_baseline_hours,
                    baseline.sleep_baseline_eff,
                    baseline.rest_baseline_ratio,
                    baseline.hrv_baseline_mu,
                    baseline.hrv_baseline_sd,
                    baseline.data_quality_score,
                    baseline.sample_days_sleep,
                    baseline.sample_days_hrv,
                    baseline.calculation_version,
                    baseline.created_at.isoformat() if baseline.created_at else now,
                    now
                ))
                conn.commit()
            return True
            
        except Exception as e:
            print(f"保存基线数据到数据库失败: {e}")
            return False
    
    def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM user_baselines WHERE user_id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # 转换为BaselineResult
                data = dict(row)
                if data['created_at']:
                    data['created_at'] = datetime.fromisoformat(data['created_at'])
                
                # 移除数据库特有字段
                data.pop('updated_at', None)
                
                return BaselineResult.from_dict(data)
                
        except Exception as e:
            print(f"从数据库读取基线数据失败: {e}")
            return None
    
    def delete_baseline(self, user_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM user_baselines WHERE user_id = ?", (user_id,))
                conn.commit()
            return True
        except Exception as e:
            print(f"从数据库删除基线数据失败: {e}")
            return False
    
    def list_users_with_baselines(self) -> List[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT user_id FROM user_baselines")
                return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
    
    def get_outdated_baselines(self, days_threshold: int = 7) -> List[str]:
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT user_id FROM user_baselines WHERE updated_at < ?",
                    (threshold_date.isoformat(),)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
    
    def get_baseline_stats(self) -> Dict[str, Any]:
        """获取基线数据统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_users,
                        AVG(data_quality_score) as avg_quality,
                        AVG(sleep_baseline_hours) as avg_sleep_hours,
                        AVG(hrv_baseline_mu) as avg_hrv_mu,
                        COUNT(CASE WHEN sleep_baseline_hours IS NOT NULL THEN 1 END) as users_with_sleep,
                        COUNT(CASE WHEN hrv_baseline_mu IS NOT NULL THEN 1 END) as users_with_hrv
                    FROM user_baselines
                """)
                row = cursor.fetchone()
                
                return {
                    'total_users': row[0],
                    'avg_quality_score': round(row[1], 3) if row[1] else 0,
                    'avg_sleep_baseline_hours': round(row[2], 2) if row[2] else None,
                    'avg_hrv_baseline_mu': round(row[3], 2) if row[3] else None,
                    'users_with_sleep_baseline': row[4],
                    'users_with_hrv_baseline': row[5]
                }
                
        except Exception as e:
            print(f"获取基线统计信息失败: {e}")
            return {}


# 默认存储实例（可配置）
_default_storage: Optional[BaselineStorage] = None

def get_default_storage() -> BaselineStorage:
    """获取默认的存储实例"""
    global _default_storage
    
    if _default_storage is None:
        # 可以通过环境变量配置存储类型
        storage_type = os.environ.get('BASELINE_STORAGE_TYPE', 'file')
        
        if storage_type == 'memory':
            _default_storage = MemoryBaselineStorage()
        elif storage_type == 'sqlite':
            db_path = os.environ.get('BASELINE_DB_PATH', 'baseline.db')
            _default_storage = SQLiteBaselineStorage(db_path)
        else:  # file
            storage_dir = os.environ.get('BASELINE_STORAGE_DIR', 'baseline_data')
            _default_storage = FileBaselineStorage(storage_dir)
    
    return _default_storage

def set_default_storage(storage: BaselineStorage):
    """设置默认存储实例"""
    global _default_storage
    _default_storage = storage