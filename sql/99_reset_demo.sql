-- Remove demonstration builds and stock movements; keeps the real BOM and price data.
TRUNCATE build, stock_movement RESTART IDENTITY;
UPDATE part SET description = NULL WHERE value_text = 'AT89S52';
