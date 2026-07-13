import zipfile
import os

# Create clean package zip
zip_name = 'SkyCore-v1.0.0-Package.zip'
print(f'Creating: {zip_name}')

# Exclude patterns
exclude_dirs = {'__pycache__', '.git', 'node_modules', 'extracted', 'tests', 'data', 'training'}
exclude_files = {'.pyc', '.pyo', '.log', '.tmp', '.zip', '.jpg', '.png'}

file_count = 0
total_size = 0

with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
    for root, dirs, files in os.walk('.'):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            # Check exclusions
            skip = False
            for ext in exclude_files:
                if file.endswith(ext):
                    skip = True
                    break
            if skip:
                continue
            
            filepath = os.path.join(root, file)
            arcname = filepath[2:]  # Remove ./
            
            try:
                zipf.write(filepath, arcname)
                file_count += 1
                total_size += os.path.getsize(filepath)
            except Exception as e:
                print(f'Skip {arcname}: {e}')

print(f'Added {file_count} files')
print(f'Total size: {total_size/1024/1024:.2f} MB')
print(f'Package: {zip_name}')