#
# Parse the Qualtrix report output for the HMS LINCS DB Download Survey
#
from __future__ import unicode_literals
import argparse
import csv
import logging
import dateutil.parser
import datetime
import json
from collections import defaultdict

logger = logging.getLogger(__name__)

LIST_DELIMITER_CSV = ';'

class DateTimeJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types and UUIDs.
    """
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if is_aware(o):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            if o.microsecond:
                r = r[:12]
            return r
        else:
            return super(DateTimeJSONEncoder, self).default(o)


parser = argparse.ArgumentParser(description='url')
parser.add_argument(
    '-f', '--file', required=True,
    help='report file from qualtrix')
parser.add_argument(
    '-s', '--start_date', required=False,
    help='start_date')
parser.add_argument(
    '-e', '--end_date', required=False,
    help='end_date')

parser.add_argument(
    '-v', '--verbose', dest='verbose', action='count',
    help="Increase verbosity (specify multiple times for more)")    

if __name__ == "__main__":
    args = parser.parse_args()
    log_level = logging.WARNING # default
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
        DEBUG=True
    logging.basicConfig(
        level=log_level, 
        format='%(msecs)d:%(module)s:%(lineno)d:%(levelname)s: %(message)s')
    
    start_date = None
    end_date = None
    if args.start_date:
        start_date = dateutil.parser.parse(args.start_date).date()
    if args.end_date:
        end_date = dateutil.parser.parse(args.end_date).date()
    if start_date is not None and end_date is None:
        raise Exception('must specify both start and end dates')
    if start_date is not None:
        if start_date > end_date:
            temp = start_date
            start_date = end_date
            end_date = temp
            
    date_recorded_field = 'RecordedDate'
    name_field = 'Q1'
    email_field = 'Q7'
    additional_comments_field = 'Q5'
    ip_address_field = 'IPAddress'
    multiple_choice_field = 'Q3'
    multiple_choice_field_text_field = 'Q3_6_TEXT'
    dataset_ids_field = 'datasetIds'
    institution_field = 'Q2'

    excluded_names = [
        'Peter Sorger','Jeremy Muhlich','Sean Erickson']
    excluded_emails = [
        'psorger@gmail.com','jeremy_muhlich@hms.harvard.edu',
        'sean_erickson@hms.harvard.edu']
    
    with open(args.file) as input_file:
        
        reader = csv.reader(input_file)
        
        header = None
        data = []
        for i,line in enumerate(reader):
            
            if i == 0:
                header = line
                continue
            if i <= 2:
                continue
            _dict = dict(zip(header,[x.strip() for x in line]))
            
            logger.debug('line: %r', _dict)
            
            _parsed = _dict.copy()
            
            date_recorded = dateutil.parser.parse(_dict[date_recorded_field]).date()
            
            if start_date is not None:
                if date_recorded < start_date or date_recorded > end_date:
                    logger.info('date out of range: %s', str(date_recorded))
                    continue
        
            if _parsed[name_field] in excluded_names:
                logger.warn('excluded name: %r, record: %r',
                    _parsed[name_field], _parsed)
                continue
            if _parsed[email_field] in excluded_emails:
                logger.warn('excluded email: %r, record: %r',
                    _parsed[email_field], _parsed)
                continue
            _parsed[date_recorded_field] = date_recorded
            
            temp = _dict[multiple_choice_field]
            if temp:
                _parsed[multiple_choice_field] = temp.split(',')
            temp = _dict[multiple_choice_field_text_field]
            if temp:
                _parsed[multiple_choice_field_text_field] = temp
            temp = _dict[dataset_ids_field]
            if temp:
                _parsed[dataset_ids_field] = temp.split(',')
            temp = _dict[institution_field]
            if temp:
                _parsed[institution_field] = temp
            
            logger.info('parsed: %r', _parsed)
            data.append(_parsed)
                
        # Create some stats
        
        stats = {}
        
        dates = sorted(set([x[date_recorded_field] for x in data]))
        stats['first_date'] = dates[0]
        stats['last_date'] = dates[-1]
        stats['total_count'] = len(data)
        stats['unique_institutions_count'] = len(set([
            x[institution_field] for x in data if institution_field in x]))
        
        dataset_ids = set()
        for x in data:
            if dataset_ids_field in x:
                dataset_ids.update(x[dataset_ids_field])
        stats['unique_datasets_count'] = len(dataset_ids)

        # question answers
        question_counts = defaultdict(int)
        for x in data:
            if multiple_choice_field in x:
                for y in x[multiple_choice_field]:
                    question_counts[y] += 1
        stats['question_counts'] = question_counts

        total_count_of_answers = sum([int(x) for x in question_counts.values()])
        question_percentages = {
            k:'%s%%' % int(round(100*float(v)/float(total_count_of_answers))) 
                for k,v in question_counts.items()}
        stats['question_percentages'] = question_percentages

        print json.dumps(stats, cls=DateTimeJSONEncoder )
                    