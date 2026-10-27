from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Conversation


@require_POST
def start(request):
    # Браузер получает только cookie сессии; ключ диалога остаётся на сервере.
    conversation = Conversation.objects.filter(
        pk=request.session.get("chat_conversation")
    ).first()
    if conversation is None:
        conversation = Conversation.objects.create()
        request.session["chat_conversation"] = str(conversation.pk)
    return JsonResponse({"socket_path": "/ws/chat/"})


@staff_member_required
@permission_required("chat.reply_conversation", raise_exception=True)
def inbox(request):
    conversations = (
        Conversation.objects.filter(messages__isnull=False).distinct()[:100]
    )
    return render(request, "chat/inbox.html", {"conversations": conversations})


@staff_member_required
@permission_required("chat.reply_conversation", raise_exception=True)
def conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    return render(
        request, "chat/conversation.html", {"conversation": conversation}
    )
