from django.db.models.query import QuerySet
from django.db import connection

import logging

logger = logging.getLogger(__name__)

ITER_LIMIT = 50
class QueryFacade(object):
    order_by = ''

class PagedRawQuerySet(object):
    """
    Implement a queryset for django-tables2 that will take a raw sql statement and 
    use LIMIT/OFFSET to paginate using the database
    (TODO: a full implementation will explore caching or chunking as needed)
    
    args:
    
    sql:            the base query to run
    sql_for_count:  the query that determines the overall count
    connection:     a django.db.connection that can be used to query the database
    
    # see django.db.models.query.QuerySet for guidance on implementation
    """
    
    def __init__(self,
                 sql=None, 
                 sql_for_count=None, 
                 connection=None,
                 order_by = [],
                 parameters = [],
                 *args,**kwargs):
        if(logger.isEnabledFor(logging.DEBUG)): 
            logger.debug(str(('--PagedRawQuerySet---',sql, sql_for_count, order_by)))
        self.connection = connection
        self.sql = sql
        self.sql_for_count = sql_for_count
        self.kwargs = kwargs
        self._order_by = order_by
        self._parameters = parameters
        
        try:
            cursor = connection.cursor()
            cursor.execute(sql_for_count, parameters)
            self._count = cursor.fetchone()[0]
            logger.info(str(('self count:', self._count)))
        except Exception, e:
            logger.error(str(('On trying to execute the query', sql_for_count,e)))
            raise e

        self.query = QueryFacade()
        
    def __len__(self):
        return self.count()
        
    def count(self,*args, **kwargs):
        return self._count
    
    def order_by(self,*args, **kwargs):
        logger.info(str(('order by', args, kwargs)))
        self._order_by = []
        for col in args:
            if(col[0]=='-'):
                col = col[1:] + ' desc ' 
            self._order_by.append(col)
        return self
    
#    # for iterable
#    def __iter__(self):
#        logger.info('__iter__ called')
#        return self            
      
    def get_sql(self):
        sql = self.sql
        if(len(self._order_by)>0):
            sql += ' order by '
            sql += ','.join(self._order_by)
        return sql
    
    def __getitem__(self,key):
        # see django.db.models.query.QuerySet for guidance on implementation
        logger.debug(str(('__getitem__ called',key)))
        if not isinstance(key, (slice, int, long)):
            raise TypeError
        assert ((not isinstance(key, slice) and (key >= 0))
                or (isinstance(key, slice) and (key.start is None or key.start >= 0)
                    and (key.stop is None or key.stop >= 0))), \
                "Negative indexing is not supported."
        
        if isinstance(key, slice):
            if(key.start > self.count()):
                raise IndexError(str(('index',key,'cannot be greater than count', self.count())))
            try:
                limited_query = self.get_sql() + " OFFSET %s LIMIT %s" # + str(start) + " LIMIT " + str(stop-start)
                if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('limited_query', limited_query,str(key.start),str(key.stop-key.start))))
                if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('key', key)))
                cursor = self.connection.cursor()
                full_params = self._parameters + [str(key.start),str(key.stop-key.start)]
                cursor.execute(limited_query,full_params)
                temp =  dictfetchall(cursor) #.fetchall()
                #logger.debug(str(('result',temp)))
                return temp
            except Exception, e:
                logger.error(str(('error in slicing routine of __getitem__',e)))
                raise e
        elif(isinstance(key,int) or isinstance(key,long)):
            if(key+1 > self.count()):
                raise IndexError(str(('index',key,'too large for count', self.count())))
            limited_query = self.get_sql() + " OFFSET %s LIMIT %s" # + str(start) + " LIMIT " + str(stop-start)
            if(logger.isEnabledFor(logging.DEBUG)): logger.debug(str(('limited_query', limited_query)))
            cursor = self.connection.cursor()
            full_params = self._parameters + [str(key),str(1)]
            cursor.execute(limited_query, full_params)
            temp =  dictfetchall(cursor) #.fetchall()
            #logger.debug(str(('result',temp)))
            if(len(temp)==0): 
                raise IndexError(str(('unknown key',key)))
            return temp[0]
        elif(key in self.kwargs):
            return self.kwargs[key]
        else:
            raise Exception(str(('unknown __getitem__ key', key)))
 
        
def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
    ]
 
            
    #========== fields discovered from runtime testing ===============
    
    #called by    RequestConfig(request, paginate={"per_page": 25}).configure(queryset) 
    # django_tables2/config.py in configure
#    def prefixed_order_by_field(self):
#        logger.info(str(('prefixed_order_by_field')))
#        return None
#    
#    def prefixed_page_field(self):
#        logger.info(str(('prefixed_page_field')))
#        return None
#    def prefixed_per_page_field(self):
#        logger.info(str(('prefixed_per_page_field')))
#        return None