import React, {useEffect, useRef, useState, type ComponentPropsWithoutRef} from 'react';
import OriginalComponents from '@theme-original/MDXComponents';

function ReferenceTable(props: ComponentPropsWithoutRef<'table'>) {
  const element = useRef<HTMLTableElement>(null);
  const [scrollable, setScrollable] = useState(false);
  useEffect(() => {
    const table = element.current;
    if (!table) return;
    const update = () => setScrollable(table.scrollWidth > table.clientWidth + 1);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(table);
    return () => observer.disconnect();
  }, []);
  return <table {...props} ref={element} tabIndex={props.tabIndex ?? (scrollable ? 0 : undefined)} />;
}

export default {...OriginalComponents, table: ReferenceTable};
