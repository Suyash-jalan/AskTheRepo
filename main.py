from pathlib import Path
import git
import os
import chromadb
import subprocess
import json
import re

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

repo_url = "https://github.com/Suyash-jalan/skillBridge-backend"
storage_path = r"C:\Users\suyash\OneDrive\Desktop\agent project\git repo extraction\clone_repo"

if not os.path.exists(storage_path):
    git.Repo.clone_from(repo_url, storage_path)
else:
    print("Repo already cloned, skipping...")

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
        identifier = node.child_by_field_name("name")
        if identifier:
            return identifier.text.decode("utf-8")
        return "<unknown>"

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


# --- Embedding function using sentence-transformers ---
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
sentence_ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def embed(text: str) -> list:
    """Generate an embedding vector for the given text."""
    return sentence_ef([text])[0]


# --- Build chunks from the repo ---
print("Scanning repo files...")
code_files = walk_repo(storage_path)
all_chunks = []
for fpath in code_files:
    try:
        all_chunks.extend(extract_chunk(fpath))
    except Exception as e:
        print(f"Warning: Could not parse {fpath}: {e}")

print(f"Extracted {len(all_chunks)} code chunks from {len(code_files)} files.")

# --- ChromaDB setup ---
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("codebase")

# Add code chunks to the collection
print("Adding code chunks to ChromaDB...")
for chunk in all_chunks:
    embedding = embed(chunk['code'])
    collection.add(
        ids=[f"{chunk['file']}:{chunk['start_line']}"],
        embeddings=[embedding],
        documents=[chunk['code']],
        metadatas=[{
            'file': chunk['file'],
            'name': chunk['name'],
            'type': chunk['type'],
            'start_line': str(chunk['start_line']),
            'end_line': str(chunk['end_line']),
        }]
    )

# --- Docs ingestion ---
docs_take = {'.md', '.txt', '.rst'}

def split_by_markdown_headers(text: str) -> list:
    """Split markdown text into sections by headers."""
    sections = []
    current_heading = "Introduction"
    current_content = []

    for line in text.split('\n'):
        header_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if header_match:
            # Save previous section
            if current_content:
                sections.append({
                    'heading': current_heading,
                    'content': '\n'.join(current_content).strip()
                })
            current_heading = header_match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections.append({
            'heading': current_heading,
            'content': '\n'.join(current_content).strip()
        })

    return sections


def inject_docs(path: str):
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for fname in filenames:
            if os.path.splitext(fname)[1].lower() in docs_take:
                file_path = os.path.join(root, fname)
                try:
                    text = open(file_path, encoding='utf-8').read()
                except Exception:
                    continue

                sections = split_by_markdown_headers(text)
                for section in sections:
                    if not section['content'].strip():
                        continue
                    embedding = embed(section['content'])
                    collection.add(
                        ids=[f"{file_path}:{section['heading']}"],
                        embeddings=[embedding],
                        documents=[section['content']],
                        metadatas=[{'file': file_path, 'heading': section['heading'], 'source_type': 'doc'}]
                    )


print("Injecting docs...")
inject_docs(storage_path)


# --- Commit history ingestion ---
def get_commit_history(repo_path, max_commits=500):
    result = subprocess.run(
        ['git', '-C', repo_path, 'log', f'-{max_commits}',
         '--pretty=format:%H|%an|%ad|%s', '--date=short'],
        capture_output=True, text=True
    )
    commits = []
    for line in result.stdout.split('\n'):
        parts = line.split('|', 3)
        if len(parts) == 4:
            sha, author, date, message = parts
            commits.append({'sha': sha, 'author': author, 'date': date, 'message': message})
    return commits


print("Ingesting commit history...")
commits = get_commit_history(storage_path)
for commit in commits:
    text = f"{commit['message']} by {commit['author']} on {commit['date']}"
    embedding = embed(text)
    collection.add(
        ids=[f"commit:{commit['sha']}"],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{'author': commit['author'], 'date': commit['date'], 'source_type': 'commit'}]
    )
print(f"Ingested {len(commits)} commits.")


# --- Agent ---
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


class CodebaseAgent:
    def __init__(self, storage_path, collection, all_chunks, groq_api_key, model="qwen/qwen3.6-27b"):
        self.storage_path = storage_path
        self.collection = collection
        self.all_chunks = all_chunks

        self.llm = ChatGroq(model=model, api_key=groq_api_key)
        self.tools = self._build_tools()

        system_prompt = """You are a codebase assistant. Always cite the exact
        file path, line numbers, or commit hash your answer is based on.
        Never answer without grounding your claims in the retrieved information."""

        self.agent = create_react_agent(self.llm, self.tools, prompt=system_prompt)

    def _build_tools(self):
        storage_path = self.storage_path
        collection = self.collection
        all_chunks = self.all_chunks

        @tool
        def vector_search_tool(query: str) -> str:
            """Semantic search over code, docs, and commit messages."""
            query_embedding = embed(query)
            results = collection.query(query_embeddings=[query_embedding], n_results=5)
            return str(results)

        @tool
        def grep_tool(search_term: str) -> str:
            """Exact string/symbol search across the repo."""
            result = subprocess.run(
                ['git', '-C', storage_path, 'grep', '-rn', search_term],
                capture_output=True, text=True
            )
            return result.stdout or "No matches found."

        @tool
        def git_log_tool(file_path: str) -> str:
            """Get commit history for a specific file."""
            result = subprocess.run(
                ['git', '-C', storage_path, 'log', '-10',
                 '--pretty=format:%h|%an|%ad|%s', '--date=short', '--', file_path],
                capture_output=True, text=True
            )
            return result.stdout or "No commits found."

        @tool
        def git_blame_tool(file_path: str, line_number: int) -> str:
            """Find who last changed a specific line and when."""
            result = subprocess.run(
                ['git', '-C', storage_path, 'blame', '-L', f'{line_number},{line_number}', file_path],
                capture_output=True, text=True
            )
            return result.stdout or "No blame info found."

        @tool
        def find_definition_tool(name: str) -> str:
            """Find where a function or class is defined by exact name."""
            matches = [c for c in all_chunks if c['name'] == name]
            return str(matches) if matches else f"No definition found for '{name}'."

        return [vector_search_tool, grep_tool, git_log_tool, git_blame_tool, find_definition_tool]

    def run(self, question: str) -> str:
        response = self.agent.invoke({
            "messages": [{"role": "user", "content": question}]
        })
        return response["messages"][-1].content


# --- Run the agent ---
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("ERROR: GROQ_API_KEY not found in environment. Check your .env file.")
    exit(1)

agent = CodebaseAgent(
    storage_path=storage_path,
    collection=collection,
    all_chunks=all_chunks,
    groq_api_key=api_key
)

answer = agent.run("Who last changed the validateToken function?")
print(answer)
