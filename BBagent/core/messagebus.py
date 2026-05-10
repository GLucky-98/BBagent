import asyncio
import json
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

import aiosqlite


DIRECT = "direct"      # 私信：一对一消息
BROADCAST = "broadcast"  # 广播：一对多消息

class MessageBus:
    """
    异步多 Agent 通信总线
    - 内存队列：微秒级收发，非阻塞
    - 异步持久化：后台批量写入 SQLite，不阻塞主路径
    - 历史查询：支持按发送者、接收者、类型、时间范围过滤
    - 用户交互：user_send / user_receive 方法
    """

    def __init__(self, db_path: str = "message_history.db"):
        self.db_path = db_path
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

        # 待持久化队列（非阻塞）
        self._pending_queue: asyncio.Queue = asyncio.Queue()

        # 后台持久化任务
        self._persist_task: Optional[asyncio.Task] = None
        self._running = True

    async def initialize(self):
        """初始化数据库并启动后台持久化任务（需要在事件循环中调用）"""
        await self._init_db()
        self._persist_task = asyncio.create_task(self._persist_worker())
        return self

    async def _init_db(self):
        """初始化 SQLite 表，开启 WAL 模式"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    msg_type TEXT NOT NULL,
                    content TEXT,
                    timestamp REAL NOT NULL,
                    extra_json TEXT
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_to_agent ON messages(to_agent)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
            await db.commit()

    async def register_agent(self, name: str):
        """注册 Agent，创建其内存队列"""
        async with self._lock:
            if name not in self._queues:
                self._queues[name] = asyncio.Queue()

    async def unregister_agent(self, name: str):
        """注销 Agent，删除队列（历史消息仍保留）"""
        async with self._lock:
            self._queues.pop(name, None)

    async def send(self, from_agent: str, to_agent: str, content: str,
                   msg_type: str = "direct", extra: Optional[dict] = None) -> bool:
        """
        发送私信到目标 Agent 的内存队列，并异步持久化
        返回 True 表示目标存在，False 表示目标未注册
        """
        async with self._lock:
            target_queue = self._queues.get(to_agent)
            if target_queue is None:
                return False

        msg = {
            "from": from_agent,
            "to": to_agent,
            "type": msg_type,
            "content": content,
            "timestamp": time.time(),
            "extra": extra or {}
        }

        # 1. 立即放入内存队列（低延迟）
        await target_queue.put(msg)

        # 2. 放入持久化队列（非阻塞）
        await self._pending_queue.put(msg)
        return True

    async def receive(self, agent_name: str, timeout: Optional[float] = None) -> Optional[dict]:
        """
        从 Agent 的内存队列接收消息
        - timeout=None: 阻塞直到有消息
        - timeout=0: 非阻塞，立即返回 None
        """
        async with self._lock:
            q = self._queues.get(agent_name)
        if q is None:
            return None
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def receive_all(self, agent_name: str) -> List[dict]:
        """
        非阻塞地取出队列中的所有消息
        返回列表可能为空（队列为空）
        """
        async with self._lock:
            q = self._queues.get(agent_name)
        if q is None:
            return []
        
        messages = []
        while True:
            try:
                msg = q.get_nowait()
                messages.append(msg)
            except asyncio.QueueEmpty:
                break
        return messages

    async def broadcast(self, from_agent: str, content: str,
                        extra: Optional[dict] = None):
        """广播消息给所有其他已注册 Agent"""
        async with self._lock:
            agents = list(self._queues.keys())
        for agent in agents:
            if agent != from_agent:
                await self.send(from_agent, agent, content, BROADCAST, extra)

    async def query_history(self,
                            to_agent: Optional[str] = None,
                            from_agent: Optional[str] = None,
                            msg_type: Optional[str] = None,
                            start_time: Optional[float] = None,
                            end_time: Optional[float] = None,
                            limit: int = 100) -> List[dict]:
        """从 SQLite 查询历史消息（支持组合过滤）"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM messages WHERE 1=1"
            params = []

            if to_agent:
                query += " AND to_agent = ?"
                params.append(to_agent)
            if from_agent:
                query += " AND from_agent = ?"
                params.append(from_agent)
            if msg_type:
                query += " AND msg_type = ?"
                params.append(msg_type)
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def _persist_worker(self):
        """后台任务：批量写入 SQLite，降低 IO 频率"""
        batch = []
        last_flush = time.time()
        BATCH_SIZE = 100
        FLUSH_INTERVAL = 0.2  # 秒

        while self._running:
            try:
                # 等待 0.1 秒或直到有消息
                msg = await asyncio.wait_for(self._pending_queue.get(), timeout=0.1)
                batch.append(msg)
                if len(batch) >= BATCH_SIZE or (time.time() - last_flush) >= FLUSH_INTERVAL:
                    await self._flush_batch(batch)
                    batch.clear()
                    last_flush = time.time()
            except asyncio.TimeoutError:
                # 超时，检查是否有积攒的批次
                if batch:
                    await self._flush_batch(batch)
                    batch.clear()
                    last_flush = time.time()

    async def _flush_batch(self, batch: List[dict]):
        """批量插入数据库"""
        if not batch:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany("""
                INSERT INTO messages (from_agent, to_agent, msg_type, content, timestamp, extra_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [(m["from"], m["to"], m["type"], m["content"],
                   m["timestamp"], json.dumps(m["extra"])) for m in batch])
            await db.commit()

    async def shutdown(self):
        """优雅关闭：停止接收新消息，等待所有待持久化消息写入"""
        self._running = False
        if self._persist_task:
            await self._persist_task
        # 最后再写一次剩余消息
        remaining = []
        while not self._pending_queue.empty():
            try:
                remaining.append(self._pending_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if remaining:
            await self._flush_batch(remaining)

    # ========== 用户交互扩展 ==========
    async def user_send(self, to_agent: str, content: str,
                        msg_type: str = "user_message", extra: Optional[dict] = None) -> bool:
        """
        用户直接发送消息给某个 Agent。
        发送者固定为 "user"
        """
        return await self.send("user", to_agent, content, msg_type, extra)

    async def register_user(self, user_id: str = "user"):
        """注册一个用户队列，让用户可以接收 Agent 的回复"""
        await self.register_agent(user_id)

    async def unregister_user(self, user_id: str = "user"):
        """注销用户队列"""
        await self.unregister_agent(user_id)

    async def user_receive(self, user_id: str = "user", timeout: Optional[float] = None) -> Optional[dict]:
        """用户收取自己的消息（需要先 register_user）"""
        return await self.receive(user_id, timeout)




# ================== 使用示例 ==================
async def main():
    # 1. 创建并初始化总线
    bus = await MessageBus("demo_async.db").initialize()

    # 2. 注册一个 Agent "alice" 和用户自身
    await bus.register_agent("alice")
    await bus.register_user()

    # 3. 模拟 Alice 的工作任务（后台异步任务）
    async def alice_worker():
        while True:
            msg = await bus.receive("alice", timeout=1.0)
            if msg is None:
                continue
            print(f"[Alice] 收到消息 from {msg['from']}: {msg['content']}")
            if msg["from"] == "user":
                # 回复用户
                await bus.send("alice", "user", f"已收到任务：{msg['content']}")
                # 模拟处理
                await asyncio.sleep(1)
                await bus.send("alice", "user", "任务处理完成")
                break  # 示例中只处理一条消息后退出
            elif msg["from"] == "bob":
                # 可以与其他 Agent 交互
                pass

    # 启动 Alice 后台任务
    alice_task = asyncio.create_task(alice_worker())

    # 4. 用户发送消息给 Alice
    await bus.user_send("alice", "请帮我计算 2+2")

    # 5. 用户收取回复
    for _ in range(2):  # 期望收到两条回复
        reply = await bus.user_receive(timeout=3.0)
        if reply:
            print(f"[用户] 收到 from {reply['from']}: {reply['content']}")
        else:
            print("[用户] 超时未收到回复")

    # 等待 Alice 任务结束
    await alice_task

    # 6. 查询历史消息（用户与 Alice 的对话）
    print("\n--- 历史消息 (最近5条) ---")
    history = await bus.query_history(limit=5)
    for h in history:
        print(f"{h['timestamp']:.2f} [{h['from_agent']}->{h['to_agent']}] {h['content']}")

    # 7. 关闭总线
    await bus.shutdown()


if __name__ == "__main__":
    asyncio.run(main())