from django.db import models
import uuid
from django.contrib.auth.models import User
from shops.models import Business, Shop

# ========================
# TAX
# ========================
class Tax(models.Model):
    TAX_TYPES = (
        ('standard', 'Standard VAT'),
        ('zero', 'Zero Rated'),
        ('exempt', 'Exempt'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)  # e.g. VAT 16%
    rate = models.DecimalField(max_digits=5, decimal_places=2)  # 16.00
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

# ========================
# CATEGORY
# ========================
class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    color = models.CharField(max_length=7, default='#FF6B35')
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['business', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

# ========================
# PRODUCT
# ========================
class Product(models.Model):
    PRODUCT_TYPES = (
        ('physical', 'Physical Product'),
        ('digital', 'Digital Product'),
        ('service', 'Service'),
    )

    VARIANT_TYPES = (
        ('none', 'No Variants'),
        ('single', 'Single Option (e.g., Size, Weight)'),
        ('multiple', 'Multiple Options (e.g., Size+Color)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')

    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='physical')
    
    # Variants
    has_variants = models.BooleanField(default=False)
    variant_type = models.CharField(max_length=20, choices=VARIANT_TYPES, default='none')
    
    # Identification
    base_barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    base_sku = models.CharField(max_length=100, unique=True, blank=True, null=True)

    # Pricing - Base prices (used as defaults for variants)
    base_cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Tax
    tax = models.ForeignKey(
        Tax,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tax_inclusive = models.BooleanField(default=True)

    # Product Details
    unit_of_measure = models.CharField(max_length=50, default='pcs')
    reorder_level = models.IntegerField(default=10)
    is_trackable = models.BooleanField(default=True)

    # Media
    image = models.ImageField(upload_to='products/', null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.business.name})"
    
    @property
    def variant_count(self):
        return self.variants.filter(is_active=True).count()
    
    @property
    def has_stock(self):
        if self.has_variants:
            return self.variants.filter(is_active=True, inventory__current_stock__gt=0).exists()
        else:
            return self.inventory.filter(current_stock__gt=0).exists()

# ========================
# PRODUCT ATTRIBUTE
# ========================
class ProductAttribute(models.Model):
    """Represents attributes like Size, Color, Weight, etc."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)  # e.g., "Size", "Color", "Weight"
    display_order = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['product', 'name']

    def __str__(self):
        return f"{self.product.name} - {self.name}"

# ========================
# PRODUCT ATTRIBUTE VALUE
# ========================
class ProductAttributeValue(models.Model):
    """Represents specific values for attributes like 'S', 'M', 'L' for Size."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)  # e.g., "S", "M", "L", "Red", "Blue"
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'value']
        unique_together = ['attribute', 'value']

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"

# ========================
# PRODUCT VARIANT
# ========================
class ProductVariant(models.Model):
    """Represents a specific variant of a product (e.g., Shirt Size M, Color Blue)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    # Variant identification
    name = models.CharField(max_length=255, blank=True, null=True)  # Auto-generated from attributes
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    
    # Pricing - Can override product base prices
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Variant-specific attributes
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight in grams")
    dimensions = models.CharField(max_length=100, blank=True, null=True, help_text="Dimensions (LxWxH)")
    image = models.ImageField(upload_to='product_variants/', null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default variant when none selected")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']
        unique_together = ['product', 'name']

    def __str__(self):
        return f"{self.product.name} - {self.name if self.name else 'Default'}"
    
    def save(self, *args, **kwargs):
        # Auto-generate variant name if not provided
        if not self.name and self.product.has_variants:
            attribute_values = self.attribute_values.all()
            if attribute_values.exists():
                self.name = " / ".join([str(av) for av in attribute_values])
        
        # Inherit pricing from parent product if not set
        if not self.cost_price and self.product.base_cost_price:
            self.cost_price = self.product.base_cost_price
        if not self.selling_price and self.product.base_selling_price:
            self.selling_price = self.product.base_selling_price
        if not self.wholesale_price and self.product.base_wholesale_price:
            self.wholesale_price = self.product.base_wholesale_price
        
        super().save(*args, **kwargs)
    
    @property
    def display_name(self):
        """Display name for the variant."""
        if self.name:
            return self.name
        elif self.product.has_variants:
            attribute_values = self.attribute_values.all()
            if attribute_values.exists():
                return " / ".join([str(av) for av in attribute_values])
        return self.product.name
    
    @property
    def effective_cost_price(self):
        """Get effective cost price (variant or product base)."""
        return self.cost_price or self.product.base_cost_price
    
    @property
    def effective_selling_price(self):
        """Get effective selling price (variant or product base)."""
        return self.selling_price or self.product.base_selling_price
    
    @property
    def effective_wholesale_price(self):
        """Get effective wholesale price (variant or product base)."""
        return self.wholesale_price or self.product.base_wholesale_price

# ========================
# PRODUCT VARIANT ATTRIBUTE
# ========================
class ProductVariantAttribute(models.Model):
    """Links variants to specific attribute values."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    value = models.ForeignKey(ProductAttributeValue, on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['variant', 'attribute']
        verbose_name = 'Variant Attribute'
        verbose_name_plural = 'Variant Attributes'

    def __str__(self):
        return f"{self.variant} - {self.attribute.name}: {self.value.value}"

# ========================
# INVENTORY
# ========================
class Inventory(models.Model):
    """Tracks inventory for products/variants per shop."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to either product (for simple products) or variant (for products with variants)
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='inventory',
        null=True,
        blank=True
    )
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        related_name='inventory',
        null=True,
        blank=True
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='inventory')

    # Stock information
    current_stock = models.IntegerField(default=0)
    reserved_stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)
    maximum_stock = models.IntegerField(null=True, blank=True)

    # Status
    last_restocked = models.DateTimeField(null=True, blank=True)
    last_movement = models.DateTimeField(null=True, blank=True)  # NEW: track latest stock movement
    is_locked = models.BooleanField(default=False)               # NEW: prevent updates during audits/sync
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ['product', 'shop'],  # For simple products
            ['variant', 'shop']   # For variant products
        ]
        verbose_name_plural = 'Inventories'
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(product__isnull=False, variant__isnull=True) |
                    models.Q(product__isnull=True, variant__isnull=False)
                ),
                name='inventory_either_product_or_variant'
            )
        ]

    def available_stock(self):
        return self.current_stock - self.reserved_stock

    def __str__(self):
        if self.variant:
            return f"{self.variant.display_name} - {self.shop.name}: {self.available_stock()}"
        else:
            return f"{self.product.name} - {self.shop.name}: {self.available_stock()}"
    
    def get_product(self):
        """Get the associated product (either directly or through variant)."""
        if self.product:
            return self.product
        elif self.variant:
            return self.variant.product
        return None

# ========================
# STOCK MOVEMENT (NEW)
# ========================
class StockMovement(models.Model):
    """Records every stock change with full audit trail."""
    MOVEMENT_TYPES = (
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('sale', 'Sale Deduction'),
        ('return', 'Customer Return'),
        ('adjustment', 'Manual Adjustment'),
        ('transfer', 'Stock Transfer'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to the affected inventory record
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='movements')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='stock_movements')

    # Denormalized fields for easier querying (optional but convenient)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)

    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # Positive for additions, negative for deductions

    reference = models.CharField(max_length=100, blank=True, null=True)  # e.g. receipt number, PO
    reason = models.CharField(max_length=255, blank=True, null=True)

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} units for {self.inventory}"

# ========================
# PRICE HISTORY
# ========================
class PriceHistory(models.Model):
    """Tracks price changes for products/variants."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to either product or variant
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='price_history',
        null=True,
        blank=True
    )
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        related_name='price_history',
        null=True,
        blank=True
    )
    
    # Price information
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_type = models.CharField(max_length=20, default='selling', choices=[
        ('cost', 'Cost Price'),
        ('selling', 'Selling Price'),
        ('wholesale', 'Wholesale Price')
    ])

    # Change information
    change_reason = models.CharField(max_length=255, blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = 'Price Histories'
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(product__isnull=False, variant__isnull=True) |
                    models.Q(product__isnull=True, variant__isnull=False)
                ),
                name='price_history_either_product_or_variant'
            )
        ]

    def __str__(self):
        target = self.variant.display_name if self.variant else self.product.name
        return f"{target} - {self.price_type}: {self.old_price} → {self.new_price}"

# ========================
# PRODUCT IMAGE
# ========================
class ProductImage(models.Model):
    """Additional images for products/variants."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to either product or variant
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='additional_images',
        null=True,
        blank=True
    )
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        related_name='additional_images',
        null=True,
        blank=True
    )
    
    image = models.ImageField(upload_to='product_images/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    display_order = models.IntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-is_primary', '-created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(product__isnull=False, variant__isnull=True) |
                    models.Q(product__isnull=True, variant__isnull=False)
                ),
                name='product_image_either_product_or_variant'
            )
        ]

    def __str__(self):
        target = self.variant.display_name if self.variant else self.product.name
        return f"Image for {target}"