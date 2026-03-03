from django import forms


class IngestForm(forms.Form):
    """Form to submit a DOI for pipeline ingestion."""

    doi = forms.CharField(
        max_length=255,
        required=True,
        label="DOI",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 10.1234/example", "size": 40}),
    )
