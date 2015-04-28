# -*- coding: utf-8 -*-
#    Copyright (C) 2014 The Patacrep Team
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from django.core.mail import mail_admins, send_mail
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from captcha.fields import CaptchaField

from generator.models import Song, Songbook, Layout, Papersize


class InlineRadioFieldRenderer(forms.widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe(u'\n%s\n' % u'\n'.join([u'%s'
                % w for w in self]))

class InlineRadioSelect(forms.widgets.RadioSelect):
    renderer = InlineRadioFieldRenderer


class RegisterForm(UserCreationForm):
    """ Require email address when a user signs up """
    captcha = CaptchaField()

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.fields['username'].help_text = _(u"30 caractères maximum.")
        self.fields['password2'].help_text = ""
        self.fields['email'].required = True

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'captcha')

    def clean_email(self):
        email = self.cleaned_data["email"]
        try:
            User.objects.get(email=email)
            raise forms.ValidationError(_(u"Cette adresse mail existe déjà. "
                                u"Si vous avez oublié votre mot de passe, "
                                u"vous pouvez le réinitialiser."))
        except User.DoesNotExist:
            return email


ADMIN_MESSAGE = _(
u'''{user_info} vous a envoyé un message depuis le site {sitename}.

================================================================
{message}
================================================================

Merci de répondre directement à son adresse mail : {sender_mail}'''
)

USER_MESSAGE = _(
u'''Vous avez envoyé un message depuis le site {sitename}. Voici
la copie reçue par les administrateurs.

================================================================
{message}
================================================================

Merci d'utiliser ce site, cordialement,
Les Administrateurs.

PS : Ce message est envoyé automatiquement. Merci de ne pas y répondre,
Les administrateurs prendont contact avec vous.'''
)


class ContactForm(forms.Form):
    subject = forms.CharField(max_length=100,
                              label=_(u"Sujet"))
    sender = forms.EmailField(label=_(u"Votre adresse mail"))
    message = forms.CharField(widget=forms.Textarea,
                              label=_(u"Votre message"))
    send_copy = forms.BooleanField(
                label=_(u"Recevoir une copie du mail"),
                required=False)

    def send_mail(self, username):
        '''Send the contact email. Data should have been cleaned before.
        '''
        message = self._make_admin_message(username)
        subject = self.cleaned_data['subject']
        mail_admins(subject, message, fail_silently=False)

        if self.cleaned_data['send_copy']:
            message = self._make_user_message()
            send_mail(subject,
                      message,
                      settings.DEFAULT_FROM_EMAIL,
                      [self.cleaned_data['sender']])

    def _make_admin_message(self, username):
        '''Adds some information in the message send to the admins
        '''
        if username is not None:
            user_info = username + " (" + self.cleaned_data['sender'] + ") "
        else:
            user_info = self.cleaned_data['sender']

        message = ADMIN_MESSAGE.format(user_info=user_info,
                 sitename=Site.objects.get_current().name,
                 message=escape(self.cleaned_data['message']),
                 sender_mail=self.cleaned_data['sender'])

        return message

    def _make_user_message(self):
        '''Adds some information in the message send to the user
        '''
        message = USER_MESSAGE.format(sitename=Site.objects.get_current().name,
                 message=escape(self.cleaned_data['message']),
                 )

        return message

def validate_latex_free(string):
        '''
        Return true if one of the LaTeX special characters
        is in the string
        '''
        TEX_CHAR, MESSAGE = forbidden_latex_chars()
        for char in TEX_CHAR:
            if char in string:
                raise ValidationError(MESSAGE)

def forbidden_latex_chars():
        '''
        Return the LaTeX special characters and a corresponding error string
        '''
        TEX_CHAR = ['\\', '{', '}', '&', '[', ']', '^', '~']
        CHARS = ', '.join(['"{char}"'.format(char=char) for char in TEX_CHAR])
        MESSAGE = _(u"Les caractères suivants sont interdits, merci de les " +
                    u"supprimer : {chars}.".format(chars=CHARS))
        return TEX_CHAR, MESSAGE

def latex_free_attributes():
    TEX_CHAR, MESSAGE = forbidden_latex_chars()
    escaped_chars = ''.join(['\\{char}'.format(char=char) for char in TEX_CHAR])
    escaped_chars = '[^'+ escaped_chars +']*'

    error_message = MESSAGE.replace("'","\\'")

    return {
        'pattern' : escaped_chars,
        'title' : error_message
    }

class SongbookCreationForm(forms.ModelForm):
    class Meta:
        model = Songbook
        fields = ('title', 'description', 'author', 'is_public')

    def __init__(self, *args, **kwargs):
        super(SongbookCreationForm, self).__init__(*args, **kwargs)
        latex_free_fields = latex_free_attributes()
        for field in ('title', 'description', 'author'):
            self.fields[field].widget.attrs.update(latex_free_fields)

    def save(self, force_insert=False, force_update=False, commit=True):
        new_songbook = super(SongbookCreationForm, self).save(commit=False)
        # User is gotten in the view
        new_songbook.user = self.user
        new_songbook.slug = slugify(new_songbook.title)

        if commit:
            new_songbook.save()
        return new_songbook

    def clean_title(self):
        title = self.cleaned_data['title']
        validate_latex_free(title)
        return title

    def clean_description(self):
        description = self.cleaned_data['description']
        validate_latex_free(description)
        return description

    def clean_author(self):
        author = self.cleaned_data["author"]
        validate_latex_free(author)
        return author


class LayoutForm(forms.ModelForm):

    class Meta:
        model = Layout
        fields = ('papersize', 'orientation', 'booktype', )

    ORIENTATIONS = (("portrait", _(u"Portrait")),
                    ("landscape", _(u"Paysage")),
                    )
    OPTIONS = [
            ('diagram', _(u"Rappel des diagrammes d'accords")),
            ('importantdiagramonly', _(u"Rappel des diagrammes importants")),
            #('repeatchords', _(u"Accords sur tous les couplets")),
            #('tabs', _(u"Tablatures")),
            #('lilypond', _(u'Partitions Lilypond')),
            ('pictures', _(u"Couvertures d'albums")),
            ('onesongperpage', _(u"Saut de page avant chaque chanson")),
            ]

    papersize = forms.ModelChoiceField(
                            queryset=Papersize.objects.all(), 
                            empty_label=None,
                            label=_("Taille"))

    orientation = forms.ChoiceField(
                            choices=ORIENTATIONS,
                            label=_("Orientation"),
                            widget=InlineRadioSelect)

    booktype = forms.ChoiceField(
                            choices=Layout.BOOKTYPES,
                            label=_("Orientation"),
                            widget=InlineRadioSelect)

    bookoptions = forms.MultipleChoiceField(
                            choices=OPTIONS,
                            label=_(u'Autres options'),
                            widget=forms.CheckboxSelectMultiple(),
                            required=False)

    def save(self, force_insert=False, force_update=False, commit=True):
        new_layout = super(LayoutForm, self).save(commit=False)
        bookoptions = self.cleaned_data.get('bookoptions', None)

        new_layout.user = self.user
        new_layout.bookoptions = bookoptions
        new_layout.other_options = {
                        "orientation": self.cleaned_data["orientation"],
                        }

        if commit:
            new_layout.save()
        return new_layout
