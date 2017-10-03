# Generate stats for the Qualtrix LINCS db download survey
# 
# Instructions:
# 1. From the eCommons website, select the "Show all applications", select the
# "Qualtrix Survey Tool"
# 2. From the Qualtrix website (https://hms.az1.qualtrics.com/ControlPanel/) 
# select the "HMS LINCS DB downloads (active)" project.
# 3. go to "Data & Analysis" and choose "Export & Import", 
# choose "Download Data Table", 
# choose: "Download all fields" and "Use choice text", export as csv.
#
# Sample run:
# 
$ PYTHONPATH=. python src/hms/qualtrix/parseReport.py  \
  -f ~/docs/work/LINCS/WebStats/Qualtrix/report20171003.csv \
  -s '2017-06-01' -e '2017-09-30' | python -m json.tool
{
    "first_date": "2017-06-01",
    "last_date": "2017-09-25",
    "question_counts": {
        "data download testing": 2,
        "further exploration of this dataset": 10,
        "integration with non-LINCS datasets": 1,
        "integration with other HMS LINCS datasets": 2,
        "integration with other LINCS datasets": 1,
        "other (Please specify below.)": 1
    },
    "question_percentages": {
        "data download testing": "12%",
        "further exploration of this dataset": "59%",
        "integration with non-LINCS datasets": "6%",
        "integration with other HMS LINCS datasets": "12%",
        "integration with other LINCS datasets": "6%",
        "other (Please specify below.)": "6%"
    },
    "total_count": 11,
    "unique_datasets_count": 10,
    "unique_institutions_count": 11
}
