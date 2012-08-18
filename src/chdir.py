import os  
import contextlib  
 
@contextlib.contextmanager  
def chdir(dirname=None): 
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)
