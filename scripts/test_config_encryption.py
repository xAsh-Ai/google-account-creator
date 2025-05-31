#!/usr/bin/env python3
"""
Configuration Encryption Testing Script

Test and validate the encryption functionality of the ConfigManager system.
"""

import sys
import os
import tempfile
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager, EncryptionManager, EncryptionError, ConfigurationError
from core.logger import get_logger

logger = get_logger("ConfigEncryptionTest")

class ConfigEncryptionTest:
    """Comprehensive test suite for configuration encryption"""
    
    def __init__(self):
        self.test_results = {}
        self.temp_dir = None
        
    def setup_test_environment(self):
        """Setup temporary test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="config_encryption_test_")
        logger.info(f"📁 Test environment created: {self.temp_dir}")
    
    def cleanup_test_environment(self):
        """Cleanup test environment"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info("🧹 Test environment cleaned up")
    
    def test_encryption_manager_basic(self):
        """Test basic EncryptionManager functionality"""
        logger.info("🔐 Testing basic encryption manager functionality")
        
        test_password = "test_password_123"
        test_data = "sensitive_api_key_12345"
        
        try:
            # Initialize encryption manager
            encryption_manager = EncryptionManager(test_password)
            
            # Test encryption
            encrypted = encryption_manager.encrypt(test_data)
            logger.debug(f"Encrypted data: {encrypted}")
            
            # Test decryption
            decrypted = encryption_manager.decrypt(encrypted)
            logger.debug(f"Decrypted data: {decrypted}")
            
            # Verify data integrity
            data_integrity = test_data == decrypted
            
            # Test encryption detection
            is_encrypted_detected = encryption_manager.is_encrypted(encrypted)
            is_plain_not_detected = not encryption_manager.is_encrypted(test_data)
            
            # Get key info
            key_info = encryption_manager.get_key_info()
            
            self.test_results['encryption_manager_basic'] = {
                'data_integrity': data_integrity,
                'encryption_detected': is_encrypted_detected,
                'plain_not_detected': is_plain_not_detected,
                'key_info_available': bool(key_info),
                'success': all([
                    data_integrity,
                    is_encrypted_detected,
                    is_plain_not_detected,
                    key_info
                ])
            }
            
            logger.info("✅ Basic encryption manager test completed")
            
        except Exception as e:
            logger.error(f"❌ Basic encryption manager test failed: {e}")
            self.test_results['encryption_manager_basic'] = {
                'success': False,
                'error': str(e)
            }
    
    def test_encryption_manager_advanced(self):
        """Test advanced encryption features"""
        logger.info("🔐 Testing advanced encryption features")
        
        test_password = "advanced_test_password_456"
        
        try:
            encryption_manager = EncryptionManager(test_password)
            
            # Test multiple encryptions of same data
            test_data = "repeated_test_data"
            encrypted1 = encryption_manager.encrypt(test_data)
            encrypted2 = encryption_manager.encrypt(test_data)
            
            # Should be different due to randomization
            different_ciphertexts = encrypted1 != encrypted2
            
            # But should decrypt to same value
            decrypted1 = encryption_manager.decrypt(encrypted1)
            decrypted2 = encryption_manager.decrypt(encrypted2)
            same_plaintexts = decrypted1 == decrypted2 == test_data
            
            # Test key rotation
            new_password = "new_advanced_password_789"
            rotation_success = encryption_manager.rotate_key(new_password)
            
            # Test that old encrypted data can still be decrypted after rotation
            try:
                post_rotation_decrypt = encryption_manager.decrypt(encrypted1)
                post_rotation_integrity = post_rotation_decrypt == test_data
            except Exception:
                post_rotation_integrity = False
            
            # Test encryption with new key
            new_encrypted = encryption_manager.encrypt("new_test_data")
            new_decrypted = encryption_manager.decrypt(new_encrypted)
            new_key_works = new_decrypted == "new_test_data"
            
            self.test_results['encryption_manager_advanced'] = {
                'different_ciphertexts': different_ciphertexts,
                'same_plaintexts': same_plaintexts,
                'key_rotation_success': rotation_success,
                'post_rotation_integrity': post_rotation_integrity,
                'new_key_works': new_key_works,
                'success': all([
                    different_ciphertexts,
                    same_plaintexts,
                    rotation_success,
                    new_key_works
                ])
            }
            
            logger.info("✅ Advanced encryption features test completed")
            
        except Exception as e:
            logger.error(f"❌ Advanced encryption features test failed: {e}")
            self.test_results['encryption_manager_advanced'] = {
                'success': False,
                'error': str(e)
            }
    
    def test_config_manager_encryption_integration(self):
        """Test ConfigManager integration with encryption"""
        logger.info("⚙️ Testing ConfigManager encryption integration")
        
        config_file = os.path.join(self.temp_dir, "test_config.json")
        encryption_key = "config_manager_test_key_123"
        
        try:
            # Initialize ConfigManager with encryption
            config_manager = ConfigManager(config_file, encryption_key)
            
            # Test setting sensitive values
            sensitive_values = {
                'sms.api_key': 'sensitive_sms_api_key_12345',
                'proxy.authentication_token': 'proxy_auth_token_67890',
                'database.password': 'super_secret_db_password'
            }
            
            # Set sensitive values
            for key, value in sensitive_values.items():
                config_manager.set(key, value)
            
            # Verify values can be retrieved
            retrieval_success = all(
                config_manager.get(key) == value
                for key, value in sensitive_values.items()
            )
            
            # Save configuration
            save_success = config_manager.save_to_file()
            
            # Verify file exists
            file_exists = os.path.exists(config_file)
            
            # Check that sensitive values are encrypted in file
            with open(config_file, 'r') as f:
                file_content = f.read()
            
            # Sensitive values should not appear in plain text
            values_not_in_plaintext = all(
                value not in file_content
                for value in sensitive_values.values()
            )
            
            # Create new ConfigManager instance to test loading
            new_config_manager = ConfigManager(config_file, encryption_key)
            
            # Verify values can be loaded and decrypted
            load_and_decrypt_success = all(
                new_config_manager.get(key) == value
                for key, value in sensitive_values.items()
            )
            
            # Test encryption status
            encryption_status = new_config_manager.get_encryption_status()
            encryption_enabled = encryption_status.get('encryption_enabled', False)
            
            # Test encryption integrity validation
            integrity_check = new_config_manager.validate_encryption_integrity()
            integrity_valid = integrity_check.get('overall_status') == 'valid'
            
            self.test_results['config_manager_encryption'] = {
                'retrieval_success': retrieval_success,
                'save_success': save_success,
                'file_exists': file_exists,
                'values_not_in_plaintext': values_not_in_plaintext,
                'load_and_decrypt_success': load_and_decrypt_success,
                'encryption_enabled': encryption_enabled,
                'integrity_valid': integrity_valid,
                'success': all([
                    retrieval_success,
                    save_success,
                    file_exists,
                    values_not_in_plaintext,
                    load_and_decrypt_success,
                    encryption_enabled,
                    integrity_valid
                ])
            }
            
            logger.info("✅ ConfigManager encryption integration test completed")
            
        except Exception as e:
            logger.error(f"❌ ConfigManager encryption integration test failed: {e}")
            self.test_results['config_manager_encryption'] = {
                'success': False,
                'error': str(e)
            }
    
    def test_encryption_error_handling(self):
        """Test encryption error handling and edge cases"""
        logger.info("🛡️ Testing encryption error handling")
        
        try:
            # Test wrong password
            encryption_manager = EncryptionManager("correct_password")
            encrypted_data = encryption_manager.encrypt("test_data")
            
            # Try to decrypt with wrong password
            wrong_password_manager = EncryptionManager("wrong_password")
            try:
                wrong_password_manager.decrypt(encrypted_data)
                wrong_password_handled = False
            except EncryptionError:
                wrong_password_handled = True
            
            # Test invalid encrypted data format
            try:
                encryption_manager.decrypt("invalid_encrypted_data")
                invalid_format_handled = False
            except EncryptionError:
                invalid_format_handled = True
            
            # Test empty data
            try:
                empty_encrypted = encryption_manager.encrypt("")
                empty_decrypted = encryption_manager.decrypt(empty_encrypted)
                empty_data_handled = empty_decrypted == ""
            except Exception:
                empty_data_handled = False
            
            # Test very long data
            try:
                long_data = "x" * 10000
                long_encrypted = encryption_manager.encrypt(long_data)
                long_decrypted = encryption_manager.decrypt(long_encrypted)
                long_data_handled = long_decrypted == long_data
            except Exception:
                long_data_handled = False
            
            # Test special characters
            try:
                special_data = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~äöüß中文🚀"
                special_encrypted = encryption_manager.encrypt(special_data)
                special_decrypted = encryption_manager.decrypt(special_encrypted)
                special_chars_handled = special_decrypted == special_data
            except Exception:
                special_chars_handled = False
            
            self.test_results['encryption_error_handling'] = {
                'wrong_password_handled': wrong_password_handled,
                'invalid_format_handled': invalid_format_handled,
                'empty_data_handled': empty_data_handled,
                'long_data_handled': long_data_handled,
                'special_chars_handled': special_chars_handled,
                'success': all([
                    wrong_password_handled,
                    invalid_format_handled,
                    empty_data_handled,
                    long_data_handled,
                    special_chars_handled
                ])
            }
            
            logger.info("✅ Encryption error handling test completed")
            
        except Exception as e:
            logger.error(f"❌ Encryption error handling test failed: {e}")
            self.test_results['encryption_error_handling'] = {
                'success': False,
                'error': str(e)
            }
    
    def test_config_export_import_encrypted(self):
        """Test encrypted configuration export and import"""
        logger.info("📤📥 Testing encrypted config export/import")
        
        config_file = os.path.join(self.temp_dir, "test_config.json")
        export_file = os.path.join(self.temp_dir, "exported_config.json")
        encryption_key = "export_import_test_key"
        
        try:
            # Setup config with encrypted data
            config_manager = ConfigManager(config_file, encryption_key)
            
            test_config = {
                'sms.api_key': 'export_test_api_key',
                'sms.provider': '5sim',
                'proxy.enabled': True,
                'proxy.http_proxy': 'http://proxy.example.com:8080',
                'account.batch_size': 10
            }
            
            for key, value in test_config.items():
                config_manager.set(key, value)
            
            # Export encrypted configuration
            export_success = config_manager.export_encrypted_config(export_file)
            
            # Verify export file exists
            export_file_exists = os.path.exists(export_file)
            
            # Create new config manager for import test
            new_config_file = os.path.join(self.temp_dir, "imported_config.json")
            import_config_manager = ConfigManager(new_config_file, encryption_key)
            
            # Import encrypted configuration
            import_success = import_config_manager.import_encrypted_config(export_file)
            
            # Verify imported data
            import_verification = all(
                import_config_manager.get(key) == value
                for key, value in test_config.items()
            )
            
            # Test with wrong encryption key
            wrong_key_manager = ConfigManager(config_file, "wrong_key")
            try:
                wrong_key_manager.import_encrypted_config(export_file)
                wrong_key_import_blocked = False
            except (EncryptionError, ConfigurationError):
                wrong_key_import_blocked = True
            
            self.test_results['config_export_import'] = {
                'export_success': export_success,
                'export_file_exists': export_file_exists,
                'import_success': import_success,
                'import_verification': import_verification,
                'wrong_key_blocked': wrong_key_import_blocked,
                'success': all([
                    export_success,
                    export_file_exists,
                    import_success,
                    import_verification,
                    wrong_key_import_blocked
                ])
            }
            
            logger.info("✅ Encrypted config export/import test completed")
            
        except Exception as e:
            logger.error(f"❌ Encrypted config export/import test failed: {e}")
            self.test_results['config_export_import'] = {
                'success': False,
                'error': str(e)
            }
    
    def test_performance_benchmarks(self):
        """Test encryption performance"""
        logger.info("⚡ Testing encryption performance")
        
        try:
            import time
            
            encryption_manager = EncryptionManager("performance_test_key")
            
            # Test data of various sizes
            test_sizes = [100, 1000, 10000, 100000]  # bytes
            performance_results = {}
            
            for size in test_sizes:
                test_data = "x" * size
                
                # Measure encryption time
                start_time = time.perf_counter()
                encrypted = encryption_manager.encrypt(test_data)
                encryption_time = time.perf_counter() - start_time
                
                # Measure decryption time
                start_time = time.perf_counter()
                decrypted = encryption_manager.decrypt(encrypted)
                decryption_time = time.perf_counter() - start_time
                
                # Verify correctness
                data_integrity = test_data == decrypted
                
                performance_results[f"{size}_bytes"] = {
                    'encryption_time': encryption_time,
                    'decryption_time': decryption_time,
                    'total_time': encryption_time + decryption_time,
                    'data_integrity': data_integrity,
                    'throughput_mb_per_sec': (size / (1024 * 1024)) / (encryption_time + decryption_time)
                }
            
            # Overall performance assessment
            all_fast_enough = all(
                result['total_time'] < 1.0  # Should complete within 1 second
                for result in performance_results.values()
            )
            
            all_data_intact = all(
                result['data_integrity']
                for result in performance_results.values()
            )
            
            self.test_results['performance_benchmarks'] = {
                'results': performance_results,
                'all_fast_enough': all_fast_enough,
                'all_data_intact': all_data_intact,
                'success': all_fast_enough and all_data_intact
            }
            
            logger.info("✅ Encryption performance test completed")
            
        except Exception as e:
            logger.error(f"❌ Encryption performance test failed: {e}")
            self.test_results['performance_benchmarks'] = {
                'success': False,
                'error': str(e)
            }
    
    def run_all_tests(self):
        """Run all encryption tests"""
        logger.info("🚀 Starting comprehensive encryption tests")
        
        try:
            self.setup_test_environment()
            
            # Run all test methods
            self.test_encryption_manager_basic()
            self.test_encryption_manager_advanced()
            self.test_config_manager_encryption_integration()
            self.test_encryption_error_handling()
            self.test_config_export_import_encrypted()
            self.test_performance_benchmarks()
            
            # Generate summary
            total_tests = len(self.test_results)
            successful_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
            
            self.test_results['summary'] = {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                'overall_success': successful_tests == total_tests
            }
            
            logger.info(f"✅ All encryption tests completed: {successful_tests}/{total_tests} passed")
            
        finally:
            self.cleanup_test_environment()
        
        return self.test_results
    
    def print_test_results(self):
        """Print detailed test results"""
        print("\n" + "="*80)
        print("🔐 CONFIGURATION ENCRYPTION TEST RESULTS")
        print("="*80)
        
        for test_name, result in self.test_results.items():
            if test_name == 'summary':
                continue
                
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"\n{status} {test_name.replace('_', ' ').title()}")
            
            if 'error' in result:
                print(f"  Error: {result['error']}")
            else:
                for key, value in result.items():
                    if key != 'success':
                        if isinstance(value, bool):
                            print(f"  {key}: {'✅' if value else '❌'}")
                        elif isinstance(value, (int, float)):
                            print(f"  {key}: {value}")
                        elif isinstance(value, dict) and key == 'results':
                            print(f"  Performance Results:")
                            for size, perf in value.items():
                                print(f"    {size}: {perf['total_time']*1000:.2f}ms")
        
        if 'summary' in self.test_results:
            summary = self.test_results['summary']
            print(f"\n{'='*80}")
            print(f"📊 SUMMARY: {summary['successful_tests']}/{summary['total_tests']} tests passed ({summary['success_rate']:.1f}%)")
            print("="*80)

def main():
    """Main function"""
    test_suite = ConfigEncryptionTest()
    
    try:
        results = test_suite.run_all_tests()
        test_suite.print_test_results()
        
        # Save results to file
        results_file = Path("profiling_results") / "config_encryption_test_results.json"
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Exit with appropriate code
        return 0 if results.get('summary', {}).get('overall_success', False) else 1
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 