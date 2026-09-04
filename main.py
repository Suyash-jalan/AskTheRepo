from pathlib import Path
import git 
 
repo_url = "https://github.com/Suyash-jalan/skillBridge-backend"
storage_path = r"C:\Users\suyash\OneDrive\Desktop\agent project\git repo extraction\clone_repo"

git.Repo.clone_from(repo_url,storage_path)

cloned_dir = Path(storage_path)

print(f"Source repo cloned at: {cloned_dir.resolve()}")