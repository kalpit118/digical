"""
Calculator Engine for DigiCal
Handles all calculator operations and expression evaluation
"""
import re

class Calculator:
    def __init__(self):
        self.memory = 0
        self.current_expression = ""
        self.last_result = 0
        
    def add_digit(self, digit):
        """Add a digit or decimal point to current expression"""
        self.current_expression += str(digit)
        return self.current_expression
    
    def add_operator(self, operator):
        """Add an operator to the expression"""
        # Prevent multiple operators in a row
        if self.current_expression and self.current_expression[-1] not in "+-×÷":
            self.current_expression += operator
        elif self.current_expression and operator == "-":
            # Allow negative numbers
            self.current_expression += operator
        return self.current_expression
    
    def clear(self):
        """Clear current expression"""
        self.current_expression = ""
        return self.current_expression
    
    def clear_entry(self):
        """Clear last entry (backspace)"""
        self.current_expression = self.current_expression[:-1]
        return self.current_expression
    
    def evaluate(self):
        """Evaluate the current expression"""
        if not self.current_expression:
            return "0"
        
        try:
            # Replace display operators with Python operators
            expression = self.current_expression.replace("×", "*").replace("÷", "/")
            
            # Handle percentage
            expression = self._handle_percentage(expression)
            
            # Strip leading zeros from integer tokens (010 -> 10)
            expression = re.sub(r'\b0+(\d+)', r'\1', expression)
            
            # Evaluate the expression
            result = eval(expression)
            
            # Format result
            if isinstance(result, float):
                # Remove trailing zeros and decimal point if whole number
                if result.is_integer():
                    result = int(result)
                else:
                    result = round(result, 8)
            
            self.last_result = result
            result_str = str(result)
            
            # Clear expression after evaluation
            self.current_expression = ""
            
            return result_str
            
        except ZeroDivisionError:
            self.current_expression = ""
            return "Error: Div by 0"
        except Exception as e:
            self.current_expression = ""
            return "Error"
    
    def _handle_percentage(self, expression):
        """Convert percentage operations"""
        # Replace X% with X/100
        expression = re.sub(r'(\d+\.?\d*)%', r'(\1/100)', expression)
        return expression
    
    def add_to_memory(self, value=None):
        """Add value to memory (M+)"""
        if value is None:
            value = self.last_result
        try:
            self.memory += float(value)
        except:
            pass
    
    def subtract_from_memory(self, value=None):
        """Subtract value from memory (M-)"""
        if value is None:
            value = self.last_result
        try:
            self.memory -= float(value)
        except:
            pass
    
    def recall_memory(self):
        """Recall memory value (MR)"""
        return str(self.memory)
    
    def clear_memory(self):
        """Clear memory (MC)"""
        self.memory = 0
    
    def get_expression(self):
        """Get current expression"""
        return self.current_expression if self.current_expression else "0"
    
    def set_expression(self, expression):
        """Set current expression"""
        self.current_expression = expression
