"""
状态管理器实现

管理代码索引系统的状态和进度更新。
"""

import asyncio
from typing import Dict, Optional
from ..interfaces import IndexingState


class CodeIndexStateManager:
    """代码索引状态管理器"""
    
    def __init__(self):
        """初始化状态管理器"""
        self.state = IndexingState.STANDBY
        self.message = ""
        self.progress = {"current": 0, "total": 0}
        self._on_progress_update = asyncio.Event()
        
    def set_system_state(self, state: IndexingState, message: str = "") -> None:
        """设置系统状态"""
        self.state = state
        self.message = message
        self._on_progress_update.set()
        self._on_progress_update.clear()
        
    def report_file_queue_progress(self, current: int, total: int, current_file: Optional[str] = None) -> None:
        """报告文件队列进度"""
        self.progress = {"current": current, "total": total, "current_file": current_file}
        self._on_progress_update.set()
        self._on_progress_update.clear()
        
    def report_block_indexing_progress(self, indexed: int, total: int) -> None:
        """报告块索引进度"""
        self.progress = {"indexed": indexed, "total": total}
        self._on_progress_update.set()
        self._on_progress_update.clear()
        
    @property
    def on_progress_update(self) -> asyncio.Event:
        """进度更新事件"""
        return self._on_progress_update
        
    def get_current_status(self) -> Dict:
        """获取当前状态"""
        return {
            "state": self.state.value,
            "message": self.message,
            "progress": self.progress
        }
        
    def dispose(self) -> None:
        """释放资源"""
        pass