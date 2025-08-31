#!/usr/bin/env python3
"""
GitDiagram++ - Repository Visualizer & Analyzer
A comprehensive tool to visualize and analyze GitHub repositories
"""

import os
import re
import ast
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import base64

try:
    import requests
    from github import Github
    import networkx as nx
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    from jinja2 import Template
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install PyGithub requests networkx matplotlib seaborn pandas jinja2")
    exit(1)

@dataclass
class FileNode:
    """Represents a file or directory in the repository"""
    path: str
    type: str  # 'file' or 'dir'
    size: int = 0
    language: str = ""
    commits: int = 0
    contributors: List[str] = None
    last_modified: str = ""

@dataclass
class Dependency:
    """Represents a dependency between modules"""
    from_file: str
    to_module: str
    import_type: str  # 'import', 'from_import'

class GitDiagramPlus:
    """Main class for repository analysis and visualization"""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.github_client = Github(github_token) if github_token else Github()
        self.repo_data = {}
        self.file_structure = {}
        self.dependencies = []
        self.commit_data = {}
        self.contributor_data = defaultdict(list)
        
    def analyze_repository(self, repo_url: str, output_dir: str = "output") -> Dict:
        """Main method to analyze a repository comprehensively"""
        print(f"🔍 Analyzing repository: {repo_url}")
        
        # Extract repo info from URL
        repo_info = self._parse_repo_url(repo_url)
        if not repo_info:
            raise ValueError("Invalid GitHub repository URL")
        
        owner, repo_name = repo_info
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Get repository object
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")
            self.repo_data = {
                'name': repo.name,
                'owner': owner,
                'description': repo.description,
                'language': repo.language,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'created_at': repo.created_at.isoformat(),
                'updated_at': repo.updated_at.isoformat()
            }
            
            print("📁 Phase 1: Analyzing file structure...")
            self._analyze_file_structure(repo)
            
            print("🔗 Phase 2: Building dependency graph...")
            self._analyze_dependencies(repo)
            
            print("📊 Phase 3: Gathering commit insights...")
            self._analyze_commit_history(repo)
            
            print("👥 Phase 4: Analyzing contributors...")
            self._analyze_contributors(repo)
            
            print("📋 Phase 5: Generating documentation...")
            self._generate_documentation(repo, output_dir)
            
            print("🎨 Phase 6: Creating visualizations...")
            self._create_visualizations(output_dir)
            
            # Generate comprehensive report
            report = self._generate_report(output_dir)
            
            print(f"✅ Analysis complete! Check the '{output_dir}' directory for results.")
            return report
            
        except Exception as e:
            print(f"❌ Error analyzing repository: {e}")
            raise
    
    def _parse_repo_url(self, url: str) -> Optional[Tuple[str, str]]:
        """Extract owner and repo name from GitHub URL"""
        patterns = [
            r'github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'github\.com/([^/]+)/([^/]+)/tree/',
            r'^([^/]+)/([^/]+)$'  # Direct format: owner/repo
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)
        return None
    
    def _analyze_file_structure(self, repo):
        """Analyze repository file structure"""
        try:
            contents = repo.get_contents("")
            self.file_structure = self._build_file_tree(repo, contents)
        except Exception as e:
            print(f"Warning: Could not analyze file structure: {e}")
    
    def _build_file_tree(self, repo, contents, path="") -> Dict:
        """Recursively build file tree structure"""
        tree = {}
        
        for content in contents:
            if content.type == "dir":
                try:
                    subcontents = repo.get_contents(content.path)
                    tree[content.name] = {
                        'type': 'dir',
                        'path': content.path,
                        'children': self._build_file_tree(repo, subcontents, content.path)
                    }
                except:
                    tree[content.name] = {'type': 'dir', 'path': content.path, 'children': {}}
            else:
                tree[content.name] = {
                    'type': 'file',
                    'path': content.path,
                    'size': content.size,
                    'language': self._detect_language(content.name)
                }
        
        return tree
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from file extension"""
        extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.r': 'R',
            '.sql': 'SQL',
            '.sh': 'Shell',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.json': 'JSON',
            '.xml': 'XML',
            '.html': 'HTML',
            '.css': 'CSS',
            '.md': 'Markdown'
        }
        
        ext = Path(filename).suffix.lower()
        return extensions.get(ext, 'Unknown')
    
    def _analyze_dependencies(self, repo):
        """Analyze code dependencies (focusing on Python)"""
        self.dependencies = []
        
        try:
            # Get all Python files
            python_files = self._get_files_by_extension(repo, '.py')
            
            for file_path in python_files:
                try:
                    file_content = repo.get_contents(file_path)
                    if file_content.size > 1000000:  # Skip very large files
                        continue
                        
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    deps = self._extract_python_imports(content, file_path)
                    self.dependencies.extend(deps)
                except Exception as e:
                    print(f"Warning: Could not analyze {file_path}: {e}")
                    
        except Exception as e:
            print(f"Warning: Dependency analysis failed: {e}")
    
    def _get_files_by_extension(self, repo, extension: str) -> List[str]:
        """Get all files with specific extension"""
        files = []
        
        def search_contents(contents, current_path=""):
            for content in contents:
                if content.type == "file" and content.name.endswith(extension):
                    files.append(content.path)
                elif content.type == "dir":
                    try:
                        subcontents = repo.get_contents(content.path)
                        search_contents(subcontents, content.path)
                    except:
                        continue
        
        try:
            initial_contents = repo.get_contents("")
            search_contents(initial_contents)
        except:
            pass
            
        return files
    
    def _extract_python_imports(self, content: str, file_path: str) -> List[Dependency]:
        """Extract import statements from Python code"""
        dependencies = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.append(Dependency(
                            from_file=file_path,
                            to_module=alias.name,
                            import_type='import'
                        ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dependencies.append(Dependency(
                            from_file=file_path,
                            to_module=node.module,
                            import_type='from_import'
                        ))
        except:
            # Fallback to regex if AST parsing fails
            import_patterns = [
                r'^\s*import\s+([^\s#]+)',
                r'^\s*from\s+([^\s#]+)\s+import'
            ]
            
            for line in content.split('\n'):
                for pattern in import_patterns:
                    match = re.match(pattern, line)
                    if match:
                        dependencies.append(Dependency(
                            from_file=file_path,
                            to_module=match.group(1),
                            import_type='import'
                        ))
        
        return dependencies
    
    def _analyze_commit_history(self, repo):
        """Analyze commit history and file change patterns"""
        try:
            # Get commits from last 6 months
            since = datetime.now() - timedelta(days=180)
            commits = list(repo.get_commits(since=since))
            
            self.commit_data = {
                'total_commits': len(commits),
                'file_changes': defaultdict(int),
                'commit_frequency': defaultdict(int),
                'authors': set()
            }
            
            for commit in commits[:100]:  # Limit to avoid rate limits
                try:
                    self.commit_data['authors'].add(commit.author.login if commit.author else 'Unknown')
                    
                    # Track daily commit frequency
                    date_key = commit.commit.author.date.strftime('%Y-%m-%d')
                    self.commit_data['commit_frequency'][date_key] += 1
                    
                    # Track file changes
                    for file in commit.files[:10]:  # Limit files per commit
                        self.commit_data['file_changes'][file.filename] += 1
                        
                        # Track contributor ownership
                        author = commit.author.login if commit.author else 'Unknown'
                        self.contributor_data[author].append(file.filename)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Warning: Commit analysis failed: {e}")
            self.commit_data = {'total_commits': 0, 'file_changes': {}, 'commit_frequency': {}, 'authors': set()}
    
    def _analyze_contributors(self, repo):
        """Analyze contributor patterns and ownership"""
        try:
            contributors = list(repo.get_contributors())
            
            # Get top contributors
            self.contributor_stats = {}
            for contributor in contributors[:20]:  # Top 20 contributors
                self.contributor_stats[contributor.login] = {
                    'contributions': contributor.contributions,
                    'files_owned': len(set(self.contributor_data.get(contributor.login, []))),
                    'primary_files': Counter(self.contributor_data.get(contributor.login, [])).most_common(5)
                }
                
        except Exception as e:
            print(f"Warning: Contributor analysis failed: {e}")
            self.contributor_stats = {}
    
    def _generate_documentation(self, repo, output_dir: str):
        """Generate auto-documentation"""
        
        # Auto-README generator
        readme_template = Template("""
# {{ repo_name }}

{{ description }}

## 📊 Repository Overview
- **Language**: {{ language }}
- **Stars**: {{ stars }}
- **Forks**: {{ forks }}
- **Created**: {{ created_at }}
- **Last Updated**: {{ updated_at }}

## 📁 Project Structure
```
{{ file_structure }}
```

## 🔗 Dependencies
{% if top_dependencies %}
### Top Dependencies:
{% for dep in top_dependencies %}
- {{ dep }}
{% endfor %}
{% endif %}

## 👥 Contributors
{% if contributors %}
### Top Contributors:
{% for contributor, stats in contributors.items() %}
- **{{ contributor }}**: {{ stats.contributions }} contributions
{% endfor %}
{% endif %}

## 📈 Activity
- Total commits analyzed: {{ total_commits }}
- Active contributors: {{ active_contributors }}

---
*Generated by GitDiagram++ - Repository Visualizer & Analyzer*
        """)
        
        # Prepare data for template
        file_structure_str = self._format_file_structure(self.file_structure)
        top_deps = list(set([dep.to_module for dep in self.dependencies[:10]]))
        
        readme_content = readme_template.render(
            repo_name=self.repo_data['name'],
            description=self.repo_data.get('description', 'No description available'),
            language=self.repo_data.get('language', 'Unknown'),
            stars=self.repo_data.get('stars', 0),
            forks=self.repo_data.get('forks', 0),
            created_at=self.repo_data.get('created_at', ''),
            updated_at=self.repo_data.get('updated_at', ''),
            file_structure=file_structure_str,
            top_dependencies=top_deps,
            contributors=dict(list(self.contributor_stats.items())[:5]),
            total_commits=self.commit_data.get('total_commits', 0),
            active_contributors=len(self.commit_data.get('authors', []))
        )
        
        # Save auto-generated README
        with open(f"{output_dir}/AUTO_README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    def _format_file_structure(self, structure: Dict, indent: int = 0) -> str:
        """Format file structure as text tree"""
        result = []
        prefix = "  " * indent
        
        for name, data in sorted(structure.items()):
            if data['type'] == 'dir':
                result.append(f"{prefix}📁 {name}/")
                if 'children' in data:
                    result.append(self._format_file_structure(data['children'], indent + 1))
            else:
                icon = self._get_file_icon(data.get('language', ''))
                result.append(f"{prefix}{icon} {name}")
        
        return '\n'.join(filter(None, result))
    
    def _get_file_icon(self, language: str) -> str:
        """Get emoji icon for file type"""
        icons = {
            'Python': '🐍',
            'JavaScript': '📜',
            'TypeScript': '📘',
            'Java': '☕',
            'C++': '⚡',
            'C': '🔧',
            'Go': '🐹',
            'Rust': '🦀',
            'HTML': '🌐',
            'CSS': '🎨',
            'Markdown': '📝',
            'JSON': '📋',
            'YAML': '⚙️'
        }
        return icons.get(language, '📄')
    
    def _create_visualizations(self, output_dir: str):
        """Create various visualizations"""
        
        # 1. File Structure Diagram (Mermaid)
        self._create_mermaid_structure_diagram(output_dir)
        
        # 2. Dependency Graph
        self._create_dependency_graph(output_dir)
        
        # 3. Commit Heatmap
        self._create_commit_heatmap(output_dir)
        
        # 4. Language Distribution
        self._create_language_distribution(output_dir)
        
        # 5. Contributor Analysis
        self._create_contributor_analysis(output_dir)
    
    def _create_mermaid_structure_diagram(self, output_dir: str):
        """Generate Mermaid.js diagram for file structure"""
        mermaid_content = ["graph TD"]
        
        def add_to_mermaid(structure: Dict, parent_id: str = "root"):
            for name, data in structure.items():
                node_id = f"{parent_id}_{name}".replace("/", "_").replace(".", "_").replace("-", "_")
                
                if data['type'] == 'dir':
                    mermaid_content.append(f'    {node_id}[📁 {name}]')
                    if parent_id != "root":
                        mermaid_content.append(f'    {parent_id} --> {node_id}')
                    
                    if 'children' in data:
                        add_to_mermaid(data['children'], node_id)
                else:
                    icon = self._get_file_icon(data.get('language', ''))
                    mermaid_content.append(f'    {node_id}[{icon} {name}]')
                    mermaid_content.append(f'    {parent_id} --> {node_id}')
        
        mermaid_content.append('    root[🏠 Repository]')
        add_to_mermaid(self.file_structure)
        
        # Create HTML file with Mermaid
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ repo_name }} - File Structure</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.6.1/mermaid.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .mermaid { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 {{ repo_name }} - File Structure</h1>
        <div class="mermaid">
{{ mermaid_diagram }}
        </div>
    </div>
    <script>
        mermaid.initialize({startOnLoad:true, theme: 'default'});
    </script>
</body>
</html>
        """
        
        html_content = Template(html_template).render(
            repo_name=self.repo_data['name'],
            mermaid_diagram='\n'.join(mermaid_content)
        )
        
        with open(f"{output_dir}/file_structure.html", 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _create_dependency_graph(self, output_dir: str):
        """Create dependency graph visualization"""
        if not self.dependencies:
            return
        
        plt.figure(figsize=(12, 8))
        
        # Create network graph
        G = nx.DiGraph()
        
        # Add nodes and edges
        for dep in self.dependencies:
            file_name = Path(dep.from_file).stem
            module_name = dep.to_module.split('.')[0]  # Get root module
            
            G.add_edge(file_name, module_name)
        
        # Draw graph
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color='lightblue', 
                              node_size=1000, alpha=0.7)
        
        # Draw edges
        nx.draw_networkx_edges(G, pos, edge_color='gray', 
                              arrows=True, arrowsize=20, alpha=0.5)
        
        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')
        
        plt.title(f"Dependency Graph - {self.repo_data['name']}", fontsize=16, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/dependency_graph.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_commit_heatmap(self, output_dir: str):
        """Create commit activity heatmap"""
        if not self.commit_data.get('commit_frequency'):
            return
        
        # Prepare data for heatmap
        dates = list(self.commit_data['commit_frequency'].keys())
        commits = list(self.commit_data['commit_frequency'].values())
        
        if not dates:
            return
        
        # Create DataFrame
        df = pd.DataFrame({
            'date': pd.to_datetime(dates),
            'commits': commits
        })
        
        df['weekday'] = df['date'].dt.day_name()
        df['week'] = df['date'].dt.isocalendar().week
        
        # Create pivot table for heatmap
        heatmap_data = df.pivot_table(values='commits', index='weekday', 
                                     columns='week', fill_value=0)
        
        plt.figure(figsize=(15, 6))
        sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='YlOrRd', 
                   cbar_kws={'label': 'Number of Commits'})
        plt.title(f"Commit Activity Heatmap - {self.repo_data['name']}", 
                 fontsize=16, fontweight='bold')
        plt.xlabel('Week of Year')
        plt.ylabel('Day of Week')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/commit_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_language_distribution(self, output_dir: str):
        """Create language distribution chart"""
        languages = defaultdict(int)
        
        def count_languages(structure: Dict):
            for name, data in structure.items():
                if data['type'] == 'file':
                    lang = data.get('language', 'Unknown')
                    languages[lang] += 1
                elif data['type'] == 'dir' and 'children' in data:
                    count_languages(data['children'])
        
        count_languages(self.file_structure)
        
        if not languages:
            return
        
        # Create pie chart
        plt.figure(figsize=(10, 8))
        
        # Filter out 'Unknown' and get top languages
        filtered_langs = {k: v for k, v in languages.items() if k != 'Unknown'}
        if len(filtered_langs) > 8:
            # Keep top 7 and group rest as 'Others'
            sorted_langs = sorted(filtered_langs.items(), key=lambda x: x[1], reverse=True)
            top_langs = dict(sorted_langs[:7])
            others_count = sum(count for _, count in sorted_langs[7:])
            if others_count > 0:
                top_langs['Others'] = others_count
            filtered_langs = top_langs
        
        labels = list(filtered_langs.keys())
        sizes = list(filtered_langs.values())
        
        colors = plt.cm.Set3(range(len(labels)))
        
        wedges, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%',
                                          colors=colors, startangle=90)
        
        plt.title(f"Language Distribution - {self.repo_data['name']}", 
                 fontsize=16, fontweight='bold')
        plt.axis('equal')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/language_distribution.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_contributor_analysis(self, output_dir: str):
        """Create contributor analysis visualization"""
        if not self.contributor_stats:
            return
        
        # Prepare data
        contributors = list(self.contributor_stats.keys())[:10]  # Top 10
        contributions = [self.contributor_stats[c]['contributions'] for c in contributors]
        
        plt.figure(figsize=(12, 6))
        
        # Create bar chart
        bars = plt.bar(range(len(contributors)), contributions, 
                      color='steelblue', alpha=0.7)
        
        # Customize chart
        plt.xlabel('Contributors')
        plt.ylabel('Number of Contributions')
        plt.title(f"Top Contributors - {self.repo_data['name']}", 
                 fontsize=16, fontweight='bold')
        plt.xticks(range(len(contributors)), contributors, rotation=45, ha='right')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/contributor_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _generate_report(self, output_dir: str) -> Dict:
        """Generate comprehensive analysis report"""
        
        # Calculate statistics
        total_files = self._count_files(self.file_structure)
        most_changed_files = sorted(self.commit_data.get('file_changes', {}).items(), 
                                   key=lambda x: x[1], reverse=True)[:10]
        
        report = {
            'repository': self.repo_data,
            'analysis_summary': {
                'total_files': total_files,
                'total_dependencies': len(self.dependencies),
                'total_commits_analyzed': self.commit_data.get('total_commits', 0),
                'active_contributors': len(self.commit_data.get('authors', [])),
                'most_changed_files': most_changed_files
            },
            'insights': self._generate_insights()
        }
        
        # Save report as JSON
        with open(f"{output_dir}/analysis_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        
        # Create summary HTML report
        self._create_html_report(report, output_dir)
        
        return report
    
    def _count_files(self, structure: Dict) -> int:
        """Count total files in structure"""
        count = 0
        for name, data in structure.items():
            if data['type'] == 'file':
                count += 1
            elif data['type'] == 'dir' and 'children' in data:
                count += self._count_files(data['children'])
        return count
    
    def _generate_insights(self) -> List[str]:
        """Generate insights based on analysis"""
        insights = []
        
        # File structure insights
        total_files = self._count_files(self.file_structure)
        if total_files > 100:
            insights.append("🏗️ Large codebase detected - consider modularization")
        
        # Dependency insights
        if len(self.dependencies) > 50:
            insights.append("🔗 High dependency count - potential for refactoring")
        
        # Commit insights
        if self.commit_data.get('total_commits', 0) > 1000:
            insights.append("📈 Very active repository with frequent commits")
        
        # Language insights
        primary_lang = self.repo_data.get('language')
        if primary_lang:
            insights.append(f"🎯 Primary language: {primary_lang}")
        
        # Contributor insights
        contributor_count = len(self.contributor_stats)
        if contributor_count > 10:
            insights.append("👥 Large contributor base - good community engagement")
        elif contributor_count < 3:
            insights.append("👤 Small contributor base - consider encouraging contributions")
        
        return insights
    
    def _create_html_report(self, report: Dict, output_dir: str):
        """Create comprehensive HTML report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ repo_name }} - Analysis Report</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }
        .card { background: white; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-item { text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .stat-number { font-size: 2em; font-weight: bold; color: #667eea; display: block; }
        .stat-label { color: #666; margin-top: 5px; }
        .insights { background: #e8f5e8; border-left: 4px solid #28a745; padding: 20px; }
        .insight-item { margin: 10px 0; padding: 8px 0; }
        .files-list { max-height: 300px; overflow-y: auto; background: #f8f9fa; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #333; }
        .nav { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .nav a { margin-right: 15px; color: #667eea; text-decoration: none; font-weight: 500; }
        .nav a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 {{ repo_name }}</h1>
            <p>{{ description }}</p>
            <p><strong>{{ language }}</strong> • ⭐ {{ stars }} • 🍴 {{ forks }}</p>
        </div>
        
        <div class="nav">
            <a href="#overview">📊 Overview</a>
            <a href="#structure">📁 Structure</a>
            <a href="#dependencies">🔗 Dependencies</a>
            <a href="#activity">📈 Activity</a>
            <a href="#insights">💡 Insights</a>
        </div>

        <div id="overview" class="card">
            <h2>📊 Repository Overview</h2>
            <div class="stat-grid">
                <div class="stat-item">
                    <span class="stat-number">{{ total_files }}</span>
                    <div class="stat-label">Total Files</div>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{{ total_dependencies }}</span>
                    <div class="stat-label">Dependencies</div>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{{ total_commits }}</span>
                    <div class="stat-label">Commits Analyzed</div>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{{ active_contributors }}</span>
                    <div class="stat-label">Active Contributors</div>
                </div>
            </div>
        </div>

        <div id="structure" class="card">
            <h2>📁 File Structure</h2>
            <p><a href="file_structure.html" target="_blank">🎨 View Interactive Diagram</a></p>
            <div class="files-list">
                <pre>{{ file_structure_text }}</pre>
            </div>
        </div>

        <div id="dependencies" class="card">
            <h2>🔗 Dependencies Analysis</h2>
            {% if dependencies %}
            <p>Dependency graph shows relationships between modules.</p>
            <p><a href="dependency_graph.png" target="_blank">📊 View Dependency Graph</a></p>
            <h3>Top Dependencies:</h3>
            <ul>
            {% for dep in top_dependencies %}
                <li><code>{{ dep }}</code></li>
            {% endfor %}
            </ul>
            {% else %}
            <p>No dependencies detected or analysis unavailable.</p>
            {% endif %}
        </div>

        <div id="activity" class="card">
            <h2>📈 Repository Activity</h2>
            {% if most_changed_files %}
            <h3>Most Frequently Changed Files:</h3>
            <ol>
            {% for file, changes in most_changed_files %}
                <li><code>{{ file }}</code> - {{ changes }} changes</li>
            {% endfor %}
            </ol>
            <p><a href="commit_heatmap.png" target="_blank">🔥 View Commit Heatmap</a></p>
            {% endif %}
            
            <p><a href="language_distribution.png" target="_blank">📊 View Language Distribution</a></p>
            <p><a href="contributor_analysis.png" target="_blank">👥 View Contributor Analysis</a></p>
        </div>

        <div id="insights" class="card">
            <h2>💡 Analysis Insights</h2>
            <div class="insights">
            {% for insight in insights %}
                <div class="insight-item">{{ insight }}</div>
            {% endfor %}
            </div>
        </div>

        <div class="card">
            <h2>📋 Generated Files</h2>
            <ul>
                <li><a href="AUTO_README.md">📝 Auto-generated README</a></li>
                <li><a href="analysis_report.json">📊 Detailed JSON Report</a></li>
                <li><a href="file_structure.html">🌳 Interactive File Structure</a></li>
                <li><a href="dependency_graph.png">🔗 Dependency Graph</a></li>
                <li><a href="commit_heatmap.png">🔥 Commit Heatmap</a></li>
                <li><a href="language_distribution.png">📈 Language Distribution</a></li>
                <li><a href="contributor_analysis.png">👥 Contributor Analysis</a></li>
            </ul>
        </div>
    </div>
</body>
</html>
        """
        
        # Get top dependencies
        dep_counter = Counter([dep.to_module for dep in self.dependencies])
        top_deps = [dep for dep, _ in dep_counter.most_common(10)]
        
        # Format file structure
        file_structure_text = self._format_file_structure(self.file_structure)
        
        html_content = Template(html_template).render(
            repo_name=report['repository']['name'],
            description=report['repository'].get('description', 'No description available'),
            language=report['repository'].get('language', 'Unknown'),
            stars=report['repository'].get('stars', 0),
            forks=report['repository'].get('forks', 0),
            total_files=report['analysis_summary']['total_files'],
            total_dependencies=report['analysis_summary']['total_dependencies'],
            total_commits=report['analysis_summary']['total_commits_analyzed'],
            active_contributors=report['analysis_summary']['active_contributors'],
            file_structure_text=file_structure_text,
            dependencies=self.dependencies,
            top_dependencies=top_deps,
            most_changed_files=report['analysis_summary']['most_changed_files'][:10],
            insights=report['insights']
        )
        
        with open(f"{output_dir}/index.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='GitDiagram++ - Repository Visualizer & Analyzer')
    parser.add_argument('repo_url', help='GitHub repository URL or owner/repo format')
    parser.add_argument('-t', '--token', help='GitHub personal access token')
    parser.add_argument('-o', '--output', default='output', help='Output directory (default: output)')
    parser.add_argument('--format', choices=['html', 'json', 'all'], default='all', 
                       help='Output format (default: all)')
    
    args = parser.parse_args()
    
    try:
        # Initialize analyzer
        analyzer = GitDiagramPlus(args.token)
        
        # Analyze repository
        report = analyzer.analyze_repository(args.repo_url, args.output)
        
        print("\n🎉 Analysis Complete!")
        print(f"📁 Results saved to: {args.output}/")
        print(f"🌐 Open {args.output}/index.html to view the complete report")
        
        # Print summary
        print("\n📋 Quick Summary:")
        print(f"  • Repository: {report['repository']['name']}")
        print(f"  • Total Files: {report['analysis_summary']['total_files']}")
        print(f"  • Dependencies: {report['analysis_summary']['total_dependencies']}")
        print(f"  • Commits Analyzed: {report['analysis_summary']['total_commits_analyzed']}")
        print(f"  • Contributors: {report['analysis_summary']['active_contributors']}")
        
        if report['insights']:
            print("\n💡 Key Insights:")
            for insight in report['insights'][:3]:
                print(f"  • {insight}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

# Example usage and demo functions
class DemoRunner:
    """Demo runner for testing the tool"""
    
    @staticmethod
    def run_demo(repo_url: str = "microsoft/vscode", token: str = None):
        """Run a demo analysis"""
        print("🚀 Running GitDiagram++ Demo")
        print("=" * 50)
        
        analyzer = GitDiagramPlus(token)
        
        try:
            report = analyzer.analyze_repository(repo_url, "demo_output")
            
            print("\n📊 Demo Results:")
            print(f"Repository: {report['repository']['name']}")
            print(f"Language: {report['repository'].get('language', 'Unknown')}")
            print(f"Files analyzed: {report['analysis_summary']['total_files']}")
            print(f"Dependencies found: {report['analysis_summary']['total_dependencies']}")
            
            print("\n💡 Sample Insights:")
            for insight in report['insights'][:3]:
                print(f"  • {insight}")
                
            print(f"\n🎨 Open demo_output/index.html to see the full visualization!")
            
        except Exception as e:
            print(f"Demo failed: {e}")

# Additional utility functions
class RepoCloner:
    """Utility to clone repositories for deeper analysis"""
    
    @staticmethod
    def clone_and_analyze(repo_url: str, local_path: str = "temp_repo") -> Dict:
        """Clone repo locally for advanced analysis"""
        try:
            # Clone repository
            subprocess.run(['git', 'clone', repo_url, local_path], 
                          check=True, capture_output=True)
            
            # Analyze local repository
            analysis = {
                'local_path': local_path,
                'line_count': RepoCloner._count_lines_of_code(local_path),
                'file_types': RepoCloner._analyze_file_types(local_path),
                'complexity': RepoCloner._analyze_complexity(local_path)
            }
            
            return analysis
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
            return {}
    
    @staticmethod
    def _count_lines_of_code(path: str) -> Dict[str, int]:
        """Count lines of code by language"""
        extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C'
        }
        
        line_counts = defaultdict(int)
        
        for root, dirs, files in os.walk(path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__']]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in extensions:
                    try:
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                        line_counts[extensions[ext]] += lines
                    except:
                        continue
        
        return dict(line_counts)
    
    @staticmethod
    def _analyze_file_types(path: str) -> Dict[str, int]:
        """Analyze distribution of file types"""
        file_types = defaultdict(int)
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                ext = Path(file).suffix.lower() or 'no_extension'
                file_types[ext] += 1
        
        return dict(file_types)
    
    @staticmethod
    def _analyze_complexity(path: str) -> Dict[str, float]:
        """Basic complexity analysis"""
        complexity = {
            'avg_file_size': 0,
            'max_file_size': 0,
            'total_files': 0
        }
        
        file_sizes = []
        
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    file_sizes.append(size)
                except:
                    continue
        
        if file_sizes:
            complexity['avg_file_size'] = sum(file_sizes) / len(file_sizes)
            complexity['max_file_size'] = max(file_sizes)
            complexity['total_files'] = len(file_sizes)
        
        return complexity

# Configuration and setup
class Config:
    """Configuration management"""
    
    @staticmethod
    def setup_github_token():
        """Setup GitHub token interactively"""
        token = input("Enter your GitHub personal access token (optional, press Enter to skip): ").strip()
        
        if token:
            # Save to environment or config file
            print("✅ Token configured for this session")
            return token
        else:
            print("⚠️ Running without token - API rate limits may apply")
            return None
    
    @staticmethod
    def get_sample_repos() -> List[str]:
        """Get list of sample repositories for testing"""
        return [
            "torvalds/linux",
            "microsoft/vscode",
            "facebook/react",
            "tensorflow/tensorflow",
            "django/django",
            "pallets/flask",
            "pandas-dev/pandas",
            "scikit-learn/scikit-learn"
        ]

# Interactive CLI interface
def interactive_mode():
    """Run the tool in interactive mode"""
    print("🎯 GitDiagram++ - Interactive Mode")
    print("=" * 40)
    
    # Get GitHub token
    token = Config.setup_github_token()
    
    # Get repository URL
    print("\n📝 Repository Input:")
    print("Formats supported:")
    print("  • https://github.com/owner/repo")
    print("  • owner/repo")
    
    sample_repos = Config.get_sample_repos()
    print(f"\n📋 Sample repos to try: {', '.join(sample_repos[:3])}")
    
    repo_url = input("\nEnter repository URL or owner/repo: ").strip()
    
    if not repo_url:
        repo_url = "microsoft/vscode"  # Default
        print(f"Using default: {repo_url}")
    
    # Get output directory
    output_dir = input("Output directory (default: output): ").strip() or "output"
    
    print(f"\n🚀 Starting analysis of {repo_url}...")
    
    try:
        analyzer = GitDiagramPlus(token)
        report = analyzer.analyze_repository(repo_url, output_dir)
        
        print(f"\n✅ Success! Open {output_dir}/index.html to view results")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # Run in interactive mode if no arguments
        sys.exit(interactive_mode())
    else:
        # Run with command line arguments
        sys.exit(main())