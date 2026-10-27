
import unittest

class AgenticCalculator:
    def __init__(self):
        self.history = []

    def perform_operation(self, operation_str):
        self.history.append(operation_str)
        try:
            # Simple eval for demonstration; restricted in real agents for safety
            result = eval(operation_str)
            return result
        except Exception as e:
            return f"Error: {e}"

# Automated Unit Tests
class TestAgenticCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = AgenticCalculator()

    def test_addition(self):
        self.assertEqual(self.calc.perform_operation("2 + 3"), 5)

    def test_subtraction(self):
        self.assertEqual(self.calc.perform_operation("10 - 4"), 6)

    def test_multiplication(self):
        self.assertEqual(self.calc.perform_operation("3 * 7"), 21)

    def test_division(self):
        self.assertEqual(self.calc.perform_operation("8 / 2"), 4.0)

    def test_division_by_zero(self):
        result = self.calc.perform_operation("5 / 0")
        self.assertIn("Error", str(result))

if __name__ == '__main__':
    unittest.main(exit=False)
