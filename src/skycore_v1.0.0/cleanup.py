import os
import shutil

# List of files/dirs to exclude from package
exclude = [
    '__pycache__', '.git', '.vscode', 'node_modules', '.mavis',
    '.pytest_cache', '__pypackages__', '.egg-info',
    '.pyc', '.pyo', '.pyd',
    'test_*.py', 
    'SkyCore-v1.0.0-20260518.zip',
    'fix_utils_imports.py', 'test_parse.py', 'test_all_modules.py',
    'integration_test.py',
    'Screenshot_*.jpg',
    '01-pc-flight-control.md', '02-smart-tracking.md', '03-cinematic-video.md',
    '04-mission-planning.md', '05-log-analysis.md', '06-streaming.md',
    'awesome-drone-repos.md', 'compatibility-matrix.md',
    'pasted-text*.txt',
]

# Clean up
for item in os.listdir('.'):
    skip = False
    for e in exclude:
        if item == e or (e.endswith('*') and item.startswith(e[:-1])):
            skip = True
            break
        if '*' not in e and item.endswith(e):
            skip = True
            break
    
    if skip:
        if os.path.isdir(item):
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                os.remove(item)
            except:
                pass
        print(f'Removed: {item}')

# Also remove pyc files
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.pyc') or f.endswith('.pyo'):
            path = os.path.join(root, f)
            try:
                os.remove(path)
            except:
                pass

print('\nCleanup complete')