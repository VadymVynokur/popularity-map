from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_category_name_ci"),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
