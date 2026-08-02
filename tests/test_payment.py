"""
Unit tests for the payment module's PaymentProcessor class.

These tests cover input validation, tax calculation, discount logic,
and the various processing flows of the PaymentProcessor.
"""

import unittest
from unittest import mock

from payment import PaymentProcessor


class TestPaymentProcessorInit(unittest.TestCase):
    """Tests for the PaymentProcessor constructor."""

    def setUp(self):
        self.processor = PaymentProcessor()

    def test_init_sets_api_keys(self):
        """The constructor should initialize the payment provider keys."""
        self.assertEqual(self.processor.stripe_key, "sk_test_EXAMPLE_NOT_REAL")
        self.assertEqual(self.processor.paypal_key, "paypal_EXAMPLE_NOT_REAL")
        self.assertEqual(self.processor.square_key, "square_EXAMPLE_NOT_REAL")


class TestPaymentValidation(unittest.TestCase):
    """Tests for the input validation logic in process_payment."""

    def setUp(self):
        self.processor = PaymentProcessor()
        self.base_kwargs = {
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "customer_data": {"email": "test@example.com"},
            "billing_address": None,
            "shipping_address": None,
            "items": [],
            "discount_code": None,
            "tax_rate": None,
            "processing_fee": 0.0,
            "metadata": {},
        }

    def test_invalid_amount_returns_error(self):
        """A non-positive amount should be rejected."""
        for bad_amount in [0, -5, None]:
            with self.subTest(amount=bad_amount):
                result = self.processor.process_payment(
                    amount=bad_amount, **self.base_kwargs
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["error"], "Invalid amount")

    def test_missing_currency_returns_error(self):
        """An empty currency should be rejected."""
        result = self.processor.process_payment(
            currency=None, **self.base_kwargs
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Currency required")

    def test_unsupported_currency_returns_error(self):
        """A currency outside the supported list should be rejected."""
        result = self.processor.process_payment(
            currency="JPY", **self.base_kwargs
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Unsupported currency")

    def test_missing_payment_method_returns_error(self):
        """An empty payment method should be rejected."""
        result = self.processor.process_payment(
            payment_method=None, **self.base_kwargs
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Payment method required")

    def test_missing_customer_email_returns_error(self):
        """Customer data without an email should be rejected."""
        result = self.processor.process_payment(
            customer_data={}, **self.base_kwargs
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Customer email required")


class TestTaxCalculation(unittest.TestCase):
    """Tests for the US/EU/UK tax calculation logic."""

    def setUp(self):
        self.processor = PaymentProcessor()
        self.base_kwargs = {
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "customer_data": {"email": "test@example.com"},
            "billing_address": None,
            "shipping_address": None,
            "items": [],
            "discount_code": None,
            "tax_rate": 1,
            "processing_fee": 0.0,
            "metadata": {},
        }

    def test_california_tax(self):
        """CA should apply 8% tax."""
        result = self.processor.process_payment(
            billing_address={"state": "CA"}, **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 8.0, places=2)

    def test_new_york_tax(self):
        """NY should apply 8.5% tax."""
        result = self.processor.process_payment(
            billing_address={"state": "NY"}, **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 8.5, places=2)

    def test_texas_tax(self):
        """TX should apply 6.25% tax."""
        result = self.processor.process_payment(
            billing_address={"state": "TX"}, **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 6.25, places=2)

    def test_florida_tax(self):
        """FL should apply 6% tax."""
        result = self.processor.process_payment(
            billing_address={"state": "FL"}, **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 6.0, places=2)

    def test_default_us_tax(self):
        """An unknown US state should apply 5% default tax."""
        result = self.processor.process_payment(
            billing_address={"state": "OH"}, **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 5.0, places=2)

    def test_eur_vat(self):
        """EUR should apply 20% VAT."""
        result = self.processor.process_payment(
            currency="EUR", **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 20.0, places=2)

    def test_gbp_vat(self):
        """GBP should apply 20% VAT."""
        result = self.processor.process_payment(
            currency="GBP", **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 20.0, places=2)

    def test_no_tax_when_tax_rate_false(self):
        """No tax should be applied when tax_rate is falsy."""
        kwargs = dict(self.base_kwargs)
        kwargs["tax_rate"] = None
        result = self.processor.process_payment(**kwargs)
        self.assertTrue(result["success"])
        self.assertEqual(result["tax_amount"], 0)


class TestDiscountCalculation(unittest.TestCase):
    """Tests for the discount code logic."""

    def setUp(self):
        self.processor = PaymentProcessor()
        self.base_kwargs = {
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "customer_data": {"email": "test@example.com"},
            "billing_address": None,
            "shipping_address": None,
            "items": [],
            "tax_rate": None,
            "processing_fee": 0.0,
            "metadata": {},
        }

    def test_save10_discount(self):
        """SAVE10 should apply a 10% discount."""
        result = self.processor.process_payment(
            discount_code="SAVE10", **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["discount_amount"], 10.0, places=2)

    def test_save20_discount(self):
        """SAVE20 should apply a 20% discount."""
        result = self.processor.process_payment(
            discount_code="SAVE20", **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["discount_amount"], 20.0, places=2)

    def test_newuser_discount_capped(self):
        """NEWUSER should be capped at $50."""
        result = self.processor.process_payment(
            discount_code="NEWUSER", **self.base_kwargs
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["discount_amount"], 50.0)

    def test_newuser_discount_uncapped_for_small_amount(self):
        """NEWUSER discount should not exceed the order amount."""
        kwargs = dict(self.base_kwargs)
        kwargs["amount"] = 100.0
        result = self.processor.process_payment(
            discount_code="NEWUSER", **kwargs
        )
        self.assertEqual(result["discount_amount"], 25.0)

    def test_loyalty_gold_discount(self):
        """Loyalty gold tier should apply 15% discount."""
        customer = {"email": "test@example.com", "tier": "gold"}
        result = self.processor.process_payment(
            discount_code="LOYALTY",
            customer_data=customer,
            **self.base_kwargs,
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["discount_amount"], 15.0, places=2)

    def test_loyalty_silver_discount(self):
        """Loyalty silver tier should apply a discount."""
        customer = {"email": "test@example.com", "tier": "silver"}
        result = self.processor.process_payment(
            discount_code="LOYALTY",
            customer_data=customer,
            **self.base_kwargs,
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["discount_amount"], 0)

    def test_no_discount_when_no_code(self):
        """No discount should be applied without a code."""
        result = self.processor.process_payment(**self.base_kwargs)
        self.assertTrue(result["success"])
        self.assertEqual(result["discount_amount"], 0)


class TestPaymentExecution(unittest.TestCase):
    """Tests for the actual payment execution flow."""

    def setUp(self):
        self.processor = PaymentProcessor()
        self.base_kwargs = {
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "customer_data": {"email": "test@example.com"},
            "billing_address": None,
            "shipping_address": None,
            "items": [],
            "discount_code": None,
            "tax_rate": None,
            "processing_fee": 0.0,
            "metadata": {},
        }

    @mock.patch("requests.post")
    def test_successful_payment_flow(self, mock_post):
        """A valid payment should return success and a transaction id."""
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"id": "txn_123"}
        result = self.processor.process_payment(**self.base_kwargs)
        self.assertTrue(result["success"])
        self.assertIn("transaction_id", result)

    @mock.patch("requests.post")
    def test_failed_payment_flow(self, mock_post):
        """A declined payment should return failure."""
        mock_post.return_value.ok = False
        result = self.processor.process_payment(**self.base_kwargs)
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
