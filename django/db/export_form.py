from django import forms

class ExportForm(forms.Form):
    type = forms.ChoiceField(label='type',
                             choices=[('csv','csv'),('excel','xls')])