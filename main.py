from pathlib import Path
import git 
import os
import chromadb
 
repo_url = "https://github.com/Suyash-jalan/skillBridge-backend"
storage_path = r"C:\Users\suyash\OneDrive\Desktop\agent project\git repo extraction\clone_repo"

git.Repo.clone_from(repo_url,storage_path)

cloned_dir = Path(storage_path)



CODE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.java', '.cpp', '.c', '.h', '.go', '.php', '.rb', '.rs', '.swift', '.kt', '.dart', '.lua'
}
IGNORE_DIRS = {
    '.git', '.venv', 'node_modules', 'dist', 'build', '__pycache__'
}

def walk_repo(path: str) -> str:
    files = []
    ext = os.path.splitext(path)[1].lower()
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in filenames:
            if ext in CODE_EXTENSIONS:
                files.append(os.path.join(root,file))
    return files

from tree_sitter import Language, Parser
import tree_sitter.python as tspython 

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

def extract_chunk(file_path):
    with open(file_path, 'rb') as f:
        source_code = f.read()
    tree = parser.parse(source_code)
    chunks = []

    def get_node_name(node, source_code):
        identifier = node.child_by_field("name")
        return identifier.text.decode("utf-8")

    def walk(node):
        if node.type in ("function_definition", "class_definition"):
            code = source_code[node.start_byte:node.end_byte].decode('utf-8')
            chunks.append({
                'file': file_path,
                'type': node.type,
                'name': get_node_name(node, source_code),
                'code': code,
                'start_line': node.start_point[0] +1,
                'end_line': node.end_point[0] +1          
            })
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return chunks


client = chromadb.PersistentClient(path = "./chroma_db")   
collection = client.get_or_create_collection("codebase")
 
        