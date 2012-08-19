import os
import os.path as op
import sys

import xls2py as xl
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

def main(path, sheet_id, modelname,
         dataslice=slice(1, None), header_row_num=0,
         app=APPNAME):

    model = iu.mo.get_model(app, modelname)
    fields = [f for f in model._meta.fields
              if not isinstance(f, iu.fl.AutoField)]

    sheet = xl.Workbook(path)[sheet_id]
    header = tuple([iu.to_python_identifier(h) for h in sheet[header_row_num]])

    types = tuple([iu.totype(f) for f in fields])
    input_table = sheet.as_table(dataslice=dataslice, header=header,
                                 types=types)

    labels = [l.lower() for l in input_table.labels]

    assert len(labels) == len(fields)

    for label, field in zip(labels, fields):
        assert label == field.name

    for i, row in enumerate(input_table):
        kw = dict(zip(labels, (cell._value for cell in row)))
        record = model(**kw)
        try:
            record.save()
        except Exception, e:
            iu.check_record(fields, labels, kw, i, e)
            exit(1)
            # import traceback as tb
            # tb.print_exc()


if __name__ == '__main__':
    nargs = len(sys.argv) - 1

    assert 3 <= nargs <= 4

    path, sheet_id, modelname = sys.argv[1:4]
    try:
        header_row_num = int(sys.argv[4])
    except IndexError:
        header_row_num = 0

    dataslice = slice(header_row_num + 1, None)

    main(path, sheet_id, modelname, dataslice=dataslice,
         header_row_num=header_row_num)
