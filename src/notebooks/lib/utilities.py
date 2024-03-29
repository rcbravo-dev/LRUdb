PACKAGE = 'LRUdb'
CWD = f'/Users/Shared/SharedProjects/Projects/LastRecentlyUsedDataBase/{PACKAGE}/'


def load_yaml(file_name: str) -> dict:
	import yaml

	path = CWD + file_name 

	with open(path, 'rt') as file:
		config = yaml.safe_load(file.read())
	return config


def setup_logging(path: str = 'configs/logging_config.yaml') -> None:
	import logging as log
	import logging.config 
	import yaml

	config = load_yaml(path)
	
	log.config.dictConfig(config)
	
	return log


def import_util(cwd: str = CWD, paths: list = ['src/lib']) -> None:
	'''Function to ensure import paths are properly updated. '''
	# Catch errors
	if isinstance(paths, str):
		paths = [paths]
	
	import sys

	import_paths = ['..'] + [cwd + p for p in paths]

	for i, path in enumerate(import_paths):
		if path not in sys.path: 
			sys.path.insert(i, path)


def convert_notebook(notebook_path: str, script_path: str, code_type: str = 'code', tag: str = 'convert_to_py') -> str:
	'''Cell metadata needs to be tagged with "convert_to_py" or "convert_to_md" prior to running script.'''
	import json
	
	with open(notebook_path, 'r') as f:
		notebook = json.load(f)
	
	# Extract code cells
	notebook_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == code_type]
	
	notebook_cells = [cell for cell in notebook_cells if 'tags' in cell['metadata']]
	
	# Extract source
	code = [cell['source'] for cell in notebook_cells if tag in cell['metadata']['tags']]
	
	# Flatten list and join code lines
	if code_type == 'code':
		code = '\n'.join([''.join(cell) for cell in code])
	elif code_type == 'markdown':
		code = '\n\n'.join([''.join(cell) for cell in code])
	
	# Write to file
	with open(script_path, 'w+') as f:
		f.write(code)
	
	# Output
	if len(code) == 0:
		print(f'No Data written to {code_type} "script_path"')
		print(f'Code cells parsed = {len(notebook_cells)}')
		print(f'Tagged cells parsed = {len(notebook_cells)}\nLength of source code = {len(code)}\n')
		print(f'Notebook converter wrote {len(code)} to {script_path}')
		return notebook
	else:
		split_path = script_path.split('/')
		split_path = '/'.join(split_path[-3:])
		print(f'Converter successfully wrote {len(code[0])} lines to {split_path}')
		

def notebook2python(filename: str, notebook: str = 'src/notebooks/', script: str = 'src/notebooks/lib/', markdown: str = 'src/markdown/') -> None:
	import pathlib
	
	notebook_path = CWD + f"{notebook}{filename}.ipynb"
	script_path = CWD + f"{script}{filename}.py"
	markdown_path = CWD + f"{markdown}{filename}.md"

	try:
		if pathlib.Path(notebook_path).is_file():
			test_passed = True
		else:
			raise FileNotFoundError(f'File not found. Check "{filename}" variable.')

	except FileNotFoundError as err:
		print(err)
		test_passed = False
		
	finally:
		if test_passed:
			convert_notebook(notebook_path, script_path, code_type='code', tag='convert_to_py')
			convert_notebook(notebook_path, markdown_path, code_type='markdown', tag='convert_to_md')


def get_or_create_eventloop():
    '''
    Prior to this func() I was erroniously receiving this error:
        RuntimeError: no running event loop

    ref : https://techoverflow.net/2020/10/01/how-to-fix-python-asyncio-runtimeerror-there-is-no-current-event-loop-in-thread/
    '''
    # Imports used when running the script in a Jupiter notebook
    import asyncio

    try:
        print('Running unmodified asyncio loop')
        return asyncio.get_event_loop().run_until_complete
    
    except RuntimeError as ex:
        
        if "There is no current event loop in thread" in str(ex):
            # Required imports when run on Jupyter NB. 
            # See markdown comments above
            print('Running nest_asyncio.apply()')

            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop().run_until_complete
    
