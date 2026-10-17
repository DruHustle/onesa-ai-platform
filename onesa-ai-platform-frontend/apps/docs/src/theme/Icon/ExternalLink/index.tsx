import React, {type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';

export default function IconExternalLink(): ReactNode {
  return <span className="sr-only" role="img" aria-label={translate({
    id: 'theme.IconExternalLink.ariaLabel',
    message: '(opens in new tab)',
    description: 'The ARIA label for the external link icon',
  })}/>;
}
