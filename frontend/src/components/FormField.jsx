import { cloneElement, isValidElement, useId } from 'react';

/**
 * Label + control + error/hint. Pass a single control element as children,
 * or use `as`/input props for a plain input.
 */
export default function FormField({ label, error, hint, required, children, className = '', as = 'input', ...inputProps }) {
  const autoId = useId();
  const id = inputProps.id || (isValidElement(children) && children.props.id) || autoId;
  const describedBy = [error ? `${id}-err` : null, hint ? `${id}-hint` : null].filter(Boolean).join(' ') || undefined;
  const controlProps = {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy,
    required: required || undefined,
  };
  let control;
  if (isValidElement(children)) {
    control = cloneElement(children, { ...controlProps, className: `control ${children.props.className || ''}`.trim() });
  } else {
    const Tag = as;
    control = <Tag className="control" {...inputProps} {...controlProps} />;
  }
  return (
    <div className={`field ${error ? 'field-error' : ''} ${className}`.trim()}>
      {label ? (
        <label htmlFor={id} className="field-label">
          {label}
          {required ? <span className="req" aria-hidden="true"> *</span> : null}
        </label>
      ) : null}
      {control}
      {hint && !error ? <div id={`${id}-hint`} className="field-hint">{hint}</div> : null}
      {error ? <div id={`${id}-err`} className="field-err" role="alert">{error}</div> : null}
    </div>
  );
}
