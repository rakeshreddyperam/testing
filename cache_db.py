"""
Simple database cache system for API responses
"""
import sqlite3
import json
import time
import os
from datetime import datetime, timedelta

class CacheDB:
    def __init__(self, db_path='cache.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the cache database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_cache(self, cache_key):
        """Get cached data if it exists and hasn't expired"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        
        cursor.execute('''
            SELECT data, expires_at FROM api_cache 
            WHERE cache_key = ? AND expires_at > ?
        ''', (cache_key, current_time))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            data_json, expires_at = result
            try:
                return json.loads(data_json)
            except json.JSONDecodeError:
                return None
        
        return None
    
    def set_cache(self, cache_key, data, ttl_seconds=300):
        """Set cache data with expiration time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        expires_at = current_time + ttl_seconds
        data_json = json.dumps(data)
        
        cursor.execute('''
            INSERT OR REPLACE INTO api_cache 
            (cache_key, data, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (cache_key, data_json, expires_at, current_time, current_time))
        
        conn.commit()
        conn.close()
    
    def clear_cache(self, cache_key=None):
        """Clear specific cache entry or all cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if cache_key:
            cursor.execute('DELETE FROM api_cache WHERE cache_key = ?', (cache_key,))
        else:
            cursor.execute('DELETE FROM api_cache')
        
        conn.commit()
        conn.close()
    
    def clear_expired(self):
        """Clear all expired cache entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        cursor.execute('DELETE FROM api_cache WHERE expires_at <= ?', (current_time,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def get_cache_info(self):
        """Get information about current cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        
        # Count total entries
        cursor.execute('SELECT COUNT(*) FROM api_cache')
        total_entries = cursor.fetchone()[0]
        
        # Count expired entries
        cursor.execute('SELECT COUNT(*) FROM api_cache WHERE expires_at <= ?', (current_time,))
        expired_entries = cursor.fetchone()[0]
        
        # Count valid entries
        valid_entries = total_entries - expired_entries
        
        conn.close()
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': expired_entries
        }

# Global cache instance
cache_db = CacheDB()