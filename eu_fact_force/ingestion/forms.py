from django import forms


class IngestForm(forms.Form):
    """Form to submit a file_id for pipeline ingestion."""

    file_id = forms.CharField(
        max_length=255,
        required=True,
        label="File ID",
        widget=forms.TextInput(attrs={"placeholder": "e.g. doc-001", "size": 40}),
    )
