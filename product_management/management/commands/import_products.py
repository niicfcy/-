import csv
from django.core.management.base import BaseCommand
from product_management.models import Product

class Command(BaseCommand):
    help = 'Import products from a CSV file'

    def handle(self, *args, **kwargs):
        with open('products.csv', 'r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                product = Product(
                    name=row['name'],
                    stock=int(row['stock']),
                    price=float(row['price'])
                )
                product.save()
                self.stdout.write(self.style.SUCCESS(f"Product '{product.name}' imported successfully"))
