from django import forms

from accounts.models import User

from .diffing import compare
from .models import ChangeSubmission, Project, ProjectMembership


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description", "current_text")
        labels = {"current_text": "Baseline document text"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "current_text": forms.Textarea(attrs={"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # The official text can only change through approved changes.
            del self.fields["current_text"]
        else:
            self.fields["current_text"].help_text = "Paste the starting version of your paper (at least 5 words)."

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Project name must be at least 3 characters.")
        return name

    def clean_current_text(self):
        text = self.cleaned_data["current_text"]
        if len(text.split()) < 5:
            raise forms.ValidationError("The baseline text must contain at least 5 words.")
        return text


class AddMemberForm(forms.Form):
    username = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=ProjectMembership.Role.choices, initial=ProjectMembership.Role.MEMBER)

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.user = None

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise forms.ValidationError(f'No user named "{username}" exists.')
        if user.role != User.Role.STUDENT:
            raise forms.ValidationError("Only student accounts can join a project as Leader or Member.")
        if ProjectMembership.objects.filter(project=self.project, user=user).exists():
            raise forms.ValidationError(f"{user.username} is already in this project.")
        self.user = user
        return username


class ChangeForm(forms.ModelForm):
    class Meta:
        model = ChangeSubmission
        fields = ("proposed_text", "tag", "note")
        widgets = {"proposed_text": forms.Textarea(attrs={"rows": 14})}

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields["tag"].choices = [("", "Choose a tag...")] + list(ChangeSubmission.Tag.choices)

    def clean(self):
        cleaned = super().clean()
        text = cleaned.get("proposed_text")
        if text is not None:
            result = compare(self.project.current_text, text)
            if result["added"] == 0 and result["removed"] == 0:
                raise forms.ValidationError("No changes detected. Edit the text before submitting.")
        return cleaned
