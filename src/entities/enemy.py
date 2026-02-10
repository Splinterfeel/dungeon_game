from src.ai.base import AI
from src.ai.enemy import SimpleEnemyAI
from src.entities.base import Actor


class Enemy(Actor):
    ai: AI = SimpleEnemyAI

    def model_post_init(self, __context=None):
        self.ai = self.ai()
