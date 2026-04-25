# F005 — pet-annotation 不 parse storage_uri，把 URI 整体当文件路径 open()

| | |
|---|---|
| 发现时间 | 2026-04-25 22:25 |
| 发现 phase | Phase 1.2 / pet-annotation Doubao 实战 |
| severity | **HIGH**（cross-repo 集成 bug，阻塞 Phase 1.2 & A1，但单仓 fix 可解） |
| 状态 | OPEN → 即将 FIXED（B-batch PR）|
| 北极星受影响维度 | Pluggability（storage 后端抽象失效）|

## 复现命令

```bash
# 1. ingest 30 张 image：pet-data 写 frames.db
python -m pet_data.cli ingest --source local_dir --params eco-data-params.yaml

# 2. 看 storage_uri 实际值
python -c "
import sqlite3
c = sqlite3.connect('/root/autodl-tmp/raw_data/frames.db')
c.row_factory = sqlite3.Row
print(repr(c.execute('SELECT storage_uri FROM frames LIMIT 1').fetchone()['storage_uri']))
"
# → 'local:///root/autodl-tmp/raw_data/frames/local_dir/cat_images_clip_0000_f00_clip_0000_f00.png'

# 3. 跑 annotation
python -m pet_annotation.cli annotate --annotator llm --modality vision \
  --params eco-annotation-params.yaml --db /root/autodl-tmp/annotation.db \
  --pet-data-db /root/autodl-tmp/raw_data/frames.db
# → processed=0 skipped=0 failed=30
# 每条错误：[Errno 2] No such file or directory: 'local:///root/autodl-tmp/raw_data/frames/local_dir/...png'
```

## 实际行为

pet-data 按 RFC 3986 URI 写入 frames.storage_uri：`local:///root/path` (scheme + 3 slash + abs path)。

pet-annotation orchestrator.py:639-640 直接用：
```python
storage_uri = await self._fetch_storage_uri(target_id)
image_path = storage_uri if storage_uri is not None else target_id
```

→ provider 收到 `image_path = 'local:///root/...'`，open() 当文件路径找不到 → 30 张全失败。

## 期望行为

orchestrator 应当 parse URI scheme：
- `local://` → 抽取 path 部分（`/root/...`）传给 provider
- `s3://` / `http(s)://` → 适当 backend 处理
- 无 scheme（裸路径） → 直接用

## 根因

pet-data 和 pet-annotation 对 storage_uri 的合同理解不一致：
- pet-data: 把它当 URI（含 scheme）
- pet-annotation: 直接当文件路径用

这是真实 cross-repo contract bug，CI 没覆盖（无 E2E ingest→annotate 集成测）。

## 修复

`pet-annotation/src/pet_annotation/teacher/orchestrator.py` 加 URI 解析 helper，在所有 storage_uri 用作 image_path 的地方调用（line 640 + line 710）。

```python
from urllib.parse import urlparse

def _resolve_image_path(storage_uri: str | None, target_id: str) -> str:
    """Resolve storage_uri (RFC 3986) to local file path or pass-through URL."""
    if not storage_uri:
        return target_id
    parsed = urlparse(storage_uri)
    if parsed.scheme in ("", "file", "local"):
        return parsed.path or storage_uri
    return storage_uri  # http/https/s3 等让 provider 处理
```

调用：
```python
image_path = _resolve_image_path(storage_uri, target_id)
```

## Retest 证据

待 fix 后跑：

```bash
python -m pet_annotation.cli annotate --annotator llm ...
# 期望 processed=30 failed=0
```

## Follow-ups

1. B-batch fix PR：`fix/pet-annotation-resolve-storage-uri-scheme` → pet-annotation
2. pet-data side 添加单测：写出的 storage_uri 必须可被 urlparse 正确解析（防止反向 drift）
3. CI 增加 cross-repo E2E 集成测（ingest 30 frame → annotate → expect 0 failure）
4. CONTEXT 评估：是否扩展该测试到 cross-repo-smoke-install workflow（Phase 11 改进）
