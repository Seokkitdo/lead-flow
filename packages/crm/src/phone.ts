// Keep international numbers intact; format domestic numbers as they are typed.
export function formatPhone(value: string): string {
  if (!/^[0-9\s-]*$/.test(value)) return value;
  const digits = value.replace(/[\s-]/g, '');
  if (digits.length > 11) return value;
  const prefix = digits.startsWith('02') ? 2 : digits.startsWith('1') ? 4 : 3;
  if (digits.length <= prefix) return digits;
  const middle = digits.startsWith('1') ? 4 : digits.length > prefix + 7 ? 4 : 3;
  return [
    digits.slice(0, prefix),
    digits.slice(prefix, prefix + middle),
    digits.slice(prefix + middle),
  ]
    .filter(Boolean)
    .join('-');
}

export function validPhone(value: string): boolean {
  if (!/^\+?[0-9][0-9\s-]*$/.test(value.trim())) return false;
  const compact = value.replace(/[\s-]/g, '');
  return /^(?:02[0-9]{7,8}|01[016789][0-9]{7,8}|0[3-6][0-9]{8}|070[0-9]{8}|080[0-9]{7}|1[0-9]{7}|\+[1-9][0-9]{7,14})$/.test(
    compact,
  );
}
