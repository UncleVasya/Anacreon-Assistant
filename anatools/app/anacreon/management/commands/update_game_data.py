import os
import sys
from time import sleep

from django.core.management import BaseCommand

sys.path.append("..")
from app.anacreon.models import GameData
from lib.anacreonlib.anacreon import Anacreon


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '-i', '--interval',
            nargs='?', type=int, default=1, const=1,
            help='Interval between updates, in minutes. Default is 1 min. Use 0 to update only once.'
        )

    def handle(self, *args, **options):
        print('%s %s, game id: %s' % (os.environ.get('ANACREON_LOGIN'), os.environ.get('ANACREON_PASSWORD'),
                                      os.environ.get('ANACREON_GAME_ID')))

        interval = options['interval']
        counter = 0
        while True:
            print('Update #%d...' % counter)
            counter += 1

            api = Anacreon(os.environ.get('ANACREON_LOGIN'), os.environ.get('ANACREON_PASSWORD'))
            api.gameID = os.environ.get('ANACREON_GAME_ID')

            game_info = api.get_game_info()
            api.sovID = game_info['userInfo']['sovereignID']
            GameData.objects.create(
                gameInfo=game_info,
                gameObjects=api.get_objects(),
                sovID=api.sovID
            )

            sleep(interval * 60)
            if interval == 0:
                break
