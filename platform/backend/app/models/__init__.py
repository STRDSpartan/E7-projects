"""Modèles de données. Importer ce paquet enregistre toutes les tables sur Base.metadata."""

from app.models.chat import Channel, Message
from app.models.forum import ForumPost, Thread
from app.models.guild import Guild, GuildJoinRequest, GuildMember, GuildRole
from app.models.notification import Notification
from app.models.post import Comment, Post, PostKind, PostLike, Visibility
from app.models.social import Friendship, FriendshipStatus
from app.models.user import AuthSession, User

__all__ = [
    "AuthSession",
    "Channel",
    "Comment",
    "ForumPost",
    "Friendship",
    "FriendshipStatus",
    "Guild",
    "GuildJoinRequest",
    "GuildMember",
    "GuildRole",
    "Message",
    "Notification",
    "Post",
    "PostKind",
    "PostLike",
    "Thread",
    "User",
    "Visibility",
]
