from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'slug', 'excerpt', 'cover_image', 'category']
        widgets = {
            'slug': forms.HiddenInput(),
        }


