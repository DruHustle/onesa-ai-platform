import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
const topics=[
 ['Engineering Onboarding', 'Follow the four-day Start Here learning path.', '/onboarding'],
 ['Architecture & Workflows', 'Explore the complete ecosystem, data and operational boundaries.', '/architecture'],
 ['Onesa Design System', 'Shared foundations, distinct products and familiar interactions.', '/docs/architecture/ONESA_DESIGN_SYSTEM'],
 ['Service design', 'Inspect backend and application interfaces.', '/docs/design/BACKEND_DESIGN'],
 ['API and contracts', 'Generated schemas, authentication and streaming.', '/api-explorer'],
 ['Database engineering', 'Actual tables, constraints, migrations and relationships.', '/database'],
 ['Model infrastructure', 'Real serving evidence and unverified targets.', '/docs/models/LOCAL_INFERENCE'],
 ['Training and evaluation', 'Separate preparation, evaluation and reviewed releases.', '/docs/training/EVALUATION'],
 ['Deployment and operations', 'Qualified local workflows and pending production work.', '/docs/deployment/LOCAL_DEVELOPMENT'],
 ['Security engineering', 'Identity boundaries, threats and secret handling.', '/docs/security/SECURITY_ARCHITECTURE'],
 ['Testing and quality', 'Regression suites and evidence limits.', '/docs/testing/TEST_STRATEGY'],
 ['Engineering roadmap', 'Ordered milestones and outstanding work.', '/docs/product/ROADMAP'],
 ['Decision records', 'Recorded tradeoffs and architecture decisions.', '/docs/adr/0002-mvp-storage-and-runtime'],
 ['Internal reports', 'Restricted manuals and technical evidence.', '/downloads'],
];
export default function Home(){return <Layout title="Engineering documentation" description="Onesa AI interactive technical documentation"><main className="portal-home"><div className="eyebrow">INTERNAL ENGINEERING / v0.3</div><h1>Onesa products.<br/><span>One engineering map.</span></h1><p className="lead">Explore the architecture, workflows and onboarding path across the Onesa ecosystem. European-based. Globally applicable.</p><div className="hero-actions"><Link className="button button--primary" to="/onboarding">Start engineering onboarding</Link><Link className="button button--secondary" to="/architecture">Architecture &amp; Workflows</Link></div><div className="topic-grid">{topics.map(([title,text,url])=><Link className="topic-card" key={title} to={url}><h2>{title}</h2><p>{text}</p><strong>Explore →</strong></Link>)}</div><details className="status-guide"><summary>How to read implementation status</summary><div className="evidence-strip"><span>✓ Implemented and tested</span><span>◌ Implemented, unverified</span><span>◇ Mock / simulated</span><span>↗ Proposed</span></div><p>Read the linked source and environment-specific evidence. Software verification does not establish hardware readiness or legal approval.</p></details><p className="source-note">Start with onboarding, then follow the product guides and technical references. Engineering and operational details remain protected; source documentation is not a compliance or funding eligibility claim.</p></main></Layout>;}
