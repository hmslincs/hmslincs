from niepel_2013 import *
import jinja2
import os

template_env = jinja2.Environment(
    loader=jinja2.PackageLoader('niepel_2013', 'templates'))
template = template_env.get_template('main.html')

html_path = create_output_path('main')

ligands = stash_get('ligands')
assert ligands, "'ligands' not found in stash -- please run ligand.py"
ligand_names = [ligand['name'] for ligand in ligands]

cell_lines = stash_get('cell_lines')
cell_lines.sort(key=lambda c: c['name'])
cell_line_names = [c['name'] for c in cell_lines]

data = {
    'ligand_names': ligand_names,
    'cell_line_names': cell_line_names,
    }

render_template(template, data, html_path, 'index.html')
