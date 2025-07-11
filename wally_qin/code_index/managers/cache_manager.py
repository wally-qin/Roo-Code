"""
缓存管理器实现

管理文件哈希缓存，用于增量索引。
"""

import os
import json
from typing import Dict, Optional


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, workspace_path: str):
        """
        初始化缓存管理器
        
        Args:
            workspace_path: 工作空间路径
        """
        self.workspace_path = workspace_path
        self.cache_file = os.path.join(workspace_path, ".code_index_cache.json")
        self.cache: Dict[str, str] = {}
        
    async def initialize(self) -> None:
        """初始化缓存"""
        await self.load_cache()
        
    async def load_cache(self) -> None:
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
        except Exception:
            self.cache = {}
            
    async def save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass
            
    def get_hash(self, file_path: str) -> Optional[str]:
        """获取文件哈希"""
        return self.cache.get(file_path)
        
    async def update_hash(self, file_path: str, file_hash: str) -> None:
        """更新文件哈希"""
        self.cache[file_path] = file_hash
        await self.save_cache()
        
    async def delete_hash(self, file_path: str) -> None:
        """删除文件哈希"""
        if file_path in self.cache:
            del self.cache[file_path]
            await self.save_cache()
            
    def get_all_hashes(self) -> Dict[str, str]:
        """获取所有哈希"""
        return self.cache.copy()
        
    async def clear_cache_file(self) -> None:
        """清空缓存文件"""
        self.cache = {}
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception:
            pass