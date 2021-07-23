import setuptools

setuptools.setup(
     name='rosem',  
     version='0.1',
     author="Georg Kempf",
     zip_safe=False,
     packages=['rosem','rosem.icons', 'rosem.config'],
     package_data={'rosem': ['*.ui',],
		'rosem/icons': ['*.png',],
		'rosem/config': ['config.conf',]},
     include_package_data=True,
     scripts=['rosem/rosemcl.py', 'rosem/rosemgui.py', 'rosem/relax.py'],)
