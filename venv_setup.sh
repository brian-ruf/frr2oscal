pip install setuptools
# pip install `python -c "import tomllib; f=open('../class/pyproject.toml','rb'); d=tomllib.load(f); print(' '.join(d['project']['dependencies']))"`
python -c "
import tomllib, subprocess, sys
with open('../class/pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
deps = d['project']['dependencies']
subprocess.run([sys.executable, '-m', 'pip', 'install'] + deps, check=True)
"
echo "/work/rr/class" > .venv/lib/python3.13/site-packages/oscal-dev.pth