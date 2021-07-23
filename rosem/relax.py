import rosem.rosemcl
from rosem.rosemcl import FastRelaxDensity, get_cli_args, fastrelax_main

args = get_cli_args()
args[0].fastrelax = True
fastrelax_main(*args)

