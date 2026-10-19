import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
const topics=[
 ['Getting started','Authenticate and make your first request.','/docs/public/quickstart'],
 ['Onesa AI Platform','Understand the platform’s available software capabilities.','/docs/public/ai-platform'],
 ['Applications','Chat, Knowledge, Agents and Travel workflows.','/docs/public/applications'],
 ['Company Portal','Public information and protected business workflows.','/docs/public/company-portal'],
 ['Robot simulation','Protected software simulation and future hardware boundaries.','/docs/public/robot'],
 ['Tutorials','Follow practical, synthetic application examples.','/tutorials'],
 ['API reference','Explore schemas, authentication and integration.','/api-explorer'],
 ['Architecture','Understand the model and application boundaries.','/architecture'],
 ['Onesa ecosystem','See how the company and product experiences fit together.','/docs/public/ecosystem'],
 ['Troubleshooting','Resolve integration and development errors.','/docs/public/troubleshooting'],
 ['Models and roadmap','Verified foundations and planned work.','/docs/public/models'],
 ['Release notes','Versions, additive changes and known limitations.','/docs/public/release-notes'],
 ['Downloads','Preview and download approved public guides.','/downloads'],
];
export default function Home(){return <Layout title="Developer documentation" description="Explore Onesa developer guides, API references, architecture, and verified capabilities of the Company Portal, AI Platform and Robot simulation."><main className="portal-home"><header className="docs-hero"><div className="eyebrow">PUBLIC DEVELOPER DOCUMENTATION / v0.3</div><h1>Build with<br/><span>Onesa.</span></h1><p className="lead">The company, AI platform and robotics software. Source-based guides, interactive architecture and clearly stated implementation limits.</p><div className="hero-actions"><Link className="button button--primary" to="/docs/public/quickstart">Get started</Link><Link className="button button--secondary" to="/assistant">Ask the documentation</Link></div></header><div className="topic-grid">{topics.map(([title,text,url])=><Link key={title} className="topic-card" to={url}><h2>{title}</h2><p>{text}</p><strong>Explore →</strong></Link>)}</div><details className="status-guide"><summary>How to read capability status</summary><div className="evidence-strip"><span>✓ Verified</span><span>◌ Implemented, unverified</span><span>◇ Mock</span><span>↗ Proposed</span></div><p>Each guide distinguishes available functionality from examples and future work. A status applies to its linked evidence and scope.</p></details><p className="source-note">Public sources are explicitly approved. Detailed engineering and operational records live in a separately protected internal experience. Documentation does not establish compliance or funding eligibility.</p></main></Layout>;}
