from __future__ import annotations

import unittest

from sampark.integrations.interfaces import (
    BankMitraDirectory,
    ConsentLedger,
    CustomerDataProvider,
    IntegrationBundle,
    find_missing_capabilities,
)
from sampark.integrations.mock_adapters import (
    MockBankMitraDirectory,
    MockConsentLedger,
    MockCustomerDataProvider,
)


class MockAdaptersSatisfyProtocolsTest(unittest.TestCase):
    def test_mock_customer_data_provider_satisfies_protocol(self):
        self.assertIsInstance(MockCustomerDataProvider(), CustomerDataProvider)

    def test_mock_consent_ledger_satisfies_protocol(self):
        self.assertIsInstance(MockConsentLedger(), ConsentLedger)

    def test_mock_bank_mitra_directory_satisfies_protocol(self):
        self.assertIsInstance(MockBankMitraDirectory(), BankMitraDirectory)

    def test_find_missing_capabilities_reports_nothing_missing_for_complete_adapter(self):
        report = find_missing_capabilities(MockCustomerDataProvider())
        self.assertEqual(report["CustomerDataProvider"], [])

    def test_find_missing_capabilities_reports_missing_methods_for_partial_object(self):
        class PartialProvider:
            def get_customer(self, customer_id):
                return None
            # list_customers deliberately not implemented

        report = find_missing_capabilities(PartialProvider())
        self.assertEqual(report["CustomerDataProvider"], ["list_customers"])


class MockCustomerDataProviderTest(unittest.TestCase):
    def test_get_customer_matches_underlying_mock_data(self):
        provider = MockCustomerDataProvider()
        customer = provider.get_customer("c001")
        self.assertEqual(customer.customer_id, "c001")
        self.assertEqual(customer.name, "Sita Devi")

    def test_unknown_customer_raises_key_error(self):
        provider = MockCustomerDataProvider()
        with self.assertRaises(KeyError):
            provider.get_customer("unknown")

    def test_list_customers_returns_all_ten(self):
        provider = MockCustomerDataProvider()
        self.assertEqual(len(provider.list_customers()), 10)


class MockConsentLedgerTest(unittest.TestCase):
    def test_seeded_consent_status_matches_mock_data(self):
        ledger = MockConsentLedger()
        # c006 is the "no consent" mock scenario.
        self.assertFalse(ledger.get_consent_status("c006"))
        self.assertTrue(ledger.get_consent_status("c001"))

    def test_record_consent_capture_updates_status_and_history(self):
        ledger = MockConsentLedger()
        self.assertFalse(ledger.get_consent_status("c006"))

        ledger.record_consent_capture(
            "c006", language="Hindi", channel="in_person_bank_mitra", bank_mitra_id="bm-1"
        )

        self.assertTrue(ledger.get_consent_status("c006"))
        history = ledger.history_for("c006")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].channel, "in_person_bank_mitra")

    def test_unknown_customer_defaults_to_no_consent(self):
        ledger = MockConsentLedger()
        self.assertFalse(ledger.get_consent_status("does-not-exist"))


class MockBankMitraDirectoryTest(unittest.TestCase):
    def test_known_mitra_id_returns_record(self):
        directory = MockBankMitraDirectory()
        mitra = directory.get_bank_mitra("bm-82900-044")
        self.assertEqual(mitra.mitra_id, "bm-82900-044")

    def test_unknown_mitra_id_raises_key_error(self):
        directory = MockBankMitraDirectory()
        with self.assertRaises(KeyError):
            directory.get_bank_mitra("does-not-exist")


class IntegrationBundleTest(unittest.TestCase):
    def test_load_customer_for_visit_overlays_live_consent_status(self):
        bundle = IntegrationBundle(
            customer_data=MockCustomerDataProvider(),
            consent_ledger=MockConsentLedger(),
            bank_mitra_directory=MockBankMitraDirectory(),
        )

        # Before any consent capture, c006 should still show no consent.
        customer = bundle.load_customer_for_visit("c006")
        self.assertFalse(customer.consent)

    def test_load_customer_for_visit_reflects_freshly_captured_consent(self):
        ledger = MockConsentLedger()
        bundle = IntegrationBundle(
            customer_data=MockCustomerDataProvider(),
            consent_ledger=ledger,
            bank_mitra_directory=MockBankMitraDirectory(),
        )

        ledger.record_consent_capture(
            "c006", language="Hindi", channel="in_person_bank_mitra", bank_mitra_id="bm-1"
        )
        customer = bundle.load_customer_for_visit("c006")

        self.assertTrue(customer.consent)


if __name__ == "__main__":
    unittest.main()
