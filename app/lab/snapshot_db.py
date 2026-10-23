import sqlite3

src = sqlite3.connect("/data/app.db")
dst = sqlite3.connect("/data/snapshot.db")
src.backup(dst)
dst.execute("PRAGMA journal_mode=DELETE")  # تک فایل، بدون -wal و -shm
dst.close()
src.close()
print("snapshot ready")
