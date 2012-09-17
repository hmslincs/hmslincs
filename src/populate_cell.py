import sys
import init_utils as iu

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------


class populate_cell(iu.populate_from_xls):
    def _init(this, path, sheetName):
        source = (path, sheetName, 1)
        target = (APPNAME, 'Cell')
        super(populate_cell, this)._init(source, target)
                                         

def main(argv=sys.argv[1:]):
    assert len(argv) == 2
    populate_cell(argv[0], argv[1])


if __name__ == '__main__':
    main()
