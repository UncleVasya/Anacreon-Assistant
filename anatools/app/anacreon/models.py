import jsonfield
from django.db import models
from django.db.models import DateTimeField
from django.utils import timezone
from simple_history.models import HistoricalRecords


class GameData(models.Model):
    gameInfo = jsonfield.JSONField()
    gameObjects = jsonfield.JSONField()
    sovID = models.PositiveIntegerField()
    timestamp = DateTimeField(default=timezone.now)
