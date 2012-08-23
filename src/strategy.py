class strategy(type):
    def __new__(mcls, name, bases, dct, _functype=type(lambda: 0)):
        for k, v in dct.items():
            if isinstance(v, _functype): dct[k] = classmethod(v)

        return super(strategy, mcls).__new__(mcls, name, bases, dct)

    def __call__(this, *args, **kwargs):
        this._init(*args, **kwargs)
        this._execute()
        # this._wrapup()


class Strategy(object):
    __metaclass__ = strategy

    def _init(this, *args, **kwargs):
        raise NotImplementedError()

    def _execute(this):
        raise NotImplementedError()

    def _wrapup(this):
        raise NotImplementedError()
