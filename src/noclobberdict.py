import itertools as it

class NoClobberDict(dict):
    """
    A dictionary whose keys may be assigned to at most once.
    """
    def __init__(self, d=(), **kwargs):
        self.update(d, **kwargs)

    def __setitem__(self, key, value):
        """
        Assign value to self[key].
        
        If self[key] exists and is not equal to value, raise a
        ValueError.
        """
        if key in self:
            v = self[key]
            if v != value:
                raise ValueError('key "%s" is already in dictionary, '
                                 'with value %s' % (str(key), str(v)))
        else:
            self.set(key, value)

    def update(self, d=(), **kw):
        """
        Update this dictionary with the values in d and **kw.

        The setting raises an exception if the updating would clobber
        an existing value.
        """
        for k, v in it.chain((d.iteritems() if hasattr(d, 'iteritems') else d),
                             kw.iteritems()):
            self[k] = v

    def set(self, key, value):
        """
        Assign value to self[key] unconditionally.
        
        Will not raise an error, even if self[key] already exists.
        """
        super(NoClobberDict, self).__setitem__(key, value)

if __name__ == '__main__':
    import unittest
    class Tests(unittest.TestCase):
        def test_setitem(self):
            """Test that new values can't clobber old ones."""
            d = NoClobberDict(x=1)
            d['x'] = 1
            self.assertRaises(ValueError, d.__setitem__, 'x', 2)

        def test_equality_test(self):
            """Tests that equality (not identity) is the only criterion
               to test for for clobbering."""
            d = NoClobberDict()
            d['x'] = []
            d['x'] = []
            self.assertRaises(ValueError, d.__setitem__, 'x', [1])
            d['y'] = None
            d['y'] = None

        def test_update(self):
            """Test that update won't clobber."""
            d = NoClobberDict(x=1)
            d.update({'x': 1})
            d.update(x=1)
            self.assertRaises(ValueError, d.update, {'x': 2})
            self.assertRaises(ValueError, d.update, x=2)

        def test_set(self):
            """Test unconditional setting of key-value pairs."""
            d = NoClobberDict(x=1)
            d.set('x', 2)

        def test_init(self):
            self.assertRaises(ValueError, NoClobberDict, {'x': 1}, x=2)
            self.assertRaises(ValueError, NoClobberDict, (('x', 1)), x=2)
            self.assertRaises(ValueError, NoClobberDict, (('x', 1), ('x', 2)))

    print "running tests"
    unittest.main()
