from pathlib import Path
import git 
import os
import chromadb
import subprocess
from langchain_text_splitters import MarkdownHeaderTextSplitter
 
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

def walk_repo(path: str) -> list:
    files = []
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in filenames:
            ext = os.path.splitext(file)[1].lower()
            if ext in CODE_EXTENSIONS:
                files.append(os.path.join(root, file))
    return files

from tree_sitter import Language, Parser
import tree_sitter_python as tspython 

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
                'start_line': node.start_point[0] + 1,
                'end_line': node.end_point[0] + 1          
            })
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return chunks


client = chromadb.PersistentClient(path = "./chroma_db")   
collection = client.get_or_create_collection("codebase")

for chunk in all_chunks:
    embedding = embed(chunk['code'])
    collection.add(
        ids = [f"{chunk['file']}:{chunk['start_line']}"],
        embeddings = [embedding],
        documents = chunk['code'],
        matadatas = [{
            'file': chunk['file'],
            'name': chunk['name'],
            'type': chunk['type'],
            'start_line': chunk['start_line'],
            'end_line': chunk['end_line'],
        }]
    )
        
docs_take={
    '.md','.txt','.rst'
}        

def inject_docs(path: str) -> list:

    for root, dirs, filenames in os.walk(path):
        for fname in filenames:
            if os.path.splitext(fname)[1].lower() in docs_take:
                path = os.path.join(root,fname)
                text = open(path).read()

            sections = split_by_markdown_headers(text)
            for section in sections:
                    embedding = embed(section['content'])
                    collection.add(
                        ids=[f"{path}:{section['heading']}"],
                        embeddings=[embedding],
                        documents=[section['content']],
                        metadatas=[{'file': path, 'heading': section['heading'], 'source_type': 'doc'}])    



def get_commit_history(repo_path, max_commits=500):
    result = subprocess.run(
        ['git', '-C', repo_path, 'log', f'-{max_commits}',
         '--pretty=format:%H|%an|%ad|%s', '--date=short'],
        capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.split('\n'):
        sha, author, date, message = line.split('|', 3)
        commits.append({'sha': sha, 'author': author, 'date': date, 'message': message})
    return commits

    for commit in coommits:
        embedding = embed(section['content'])
        collection.add(
            ids=[f"{path}:{section['heading']}"],
            embeddings = [embedding],
            documents = commit['content'],
            metadatas = [{'Author':section['author'],'date':section['date'],'source_type':'commit'}]
        )

def git_blame_tool(file_path, line_number, repo_path):
    result = subprocess.run(
        ['git', '-C', repo_path, 'blame', '-L', f'{line_number},{line_number}', file_path],
        capture_output=True, text=True
    )
    return  result.stdout         