#!/usr/bin/env python3
"""Build a curated skills dictionary and supporting excerpts from the local catalog.

Definitions were curated by reviewing every source course title and description.
The final field lists representative source-row indexes, not an exhaustive
course-to-skill mapping. Synonyms support future text lookup; they do not imply
that every named variant is taught in the source courses.
"""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / 'processed data' / 'eller_courses_combined.csv'
# name | category suffix (T = Technical, P = Professional) | literal aliases | source rows
DEFINITIONS = r'''
SQL|T/Database|sql;structured query language;postgresql;t-sql;mysql;relational query|85
Financial Accounting|T/Accounting|financial accounting;intermediate accounting|0,2@financial and managerial accounting,4,5,6,7
Managerial Accounting|T/Accounting|managerial accounting;management accounting|1,2,3
Financial Statement Preparation|T/Accounting|preparing financial statements;financial statement preparation;aggregating them into financial statements;pro-forma financial statements;proforma statements|0@preparing and analyzing financial statements,2@preparing and analyzing financial statements,7,10,123
Financial Statement Analysis|T/Accounting|financial statement analysis;analysis of financial statements;analyzing financial statements;reading/interpreting financial statements;financial statement (ratio) analysis|0,2,6,7@reviewing its financial statements,10,99,101,109
Financial Reporting|T/Accounting|financial reporting;reporting of financial statement items;financial statement reporting|4,5,12
Accounting Transaction Recording|T/Accounting|recording accounting transactions;accounting transactions;transaction recording|6
Asset and Revenue Accounting|T/Accounting|accounting for assets;assets and revenues;asset accounting;revenue accounting|0,4
Liability and Equity Accounting|T/Accounting|liabilities and stockholders' equity;liabilities and equity;owners' equity|0,5
Cost Accounting|T/Accounting|cost accounting;cost and managerial accounting;costing|3
Cost Allocation|T/Accounting|cost allocation;allocating support costs;allocation of costs|1,3
Cost-Volume-Profit Analysis|T/Accounting|cost volume profit analysis;cost-volume-profit analysis;cvp analysis|3
Job Costing|T/Accounting|job costing;job-order costing;job order costing|3
Process Costing|T/Accounting|process costing;process cost accounting|3
Standard Costing|T/Accounting|standard costing;standard cost accounting|3
Budgeting|T/Accounting|budgeting;budgets;merchandise budgeting|1,3,138,223
Federal Taxation|T/Accounting|federal taxation;federal tax;tax computations|8
Tax Compliance|T/Accounting|tax compliance;tax filing compliance|8
Tax Planning|T/Accounting|tax planning;minimize taxes;tax minimization|8
Assurance Services|T/Accounting|assurance services;information quality and assurance|9
Internal Controls|T/Accounting|internal control;internal controls;internal control systems|9,11
Accounting Information Systems|T/Accounting|accounting information systems;accounting information system;ais|11
Governmental Accounting|T/Accounting|governmental accounting;accounting for governmental;public sector accounting|12
Nonprofit Accounting|T/Accounting|not-for-profit entities;nonprofit accounting;not-for-profit accounting|12
Fund Accounting|T/Accounting|fund accounting;governmental fund accounting|12
GAAP|T/Accounting|gaap;generally accepted accounting principles|12
Financial Management|T/Finance|financial management;financial decision making;financial decision-making;financial problems|99,101,102,103,108,109,110
Financial Analysis|T/Finance|financial analysis;analyzing financial information;financial and economic operations|23,107,121
Financial Forecasting|T/Finance|forecasting of income and cash flows;financial statement analysis and forecasting;financial forecasting;forecasting pro forma financial statements|10,99
Company Valuation|T/Finance|company valuation;firm valuation;valuation techniques;value projects and firms;valuing stocks and bonds|10,101,103,108@valuation,112@valuation tools,120,121
Discounted Cash Flow Valuation|T/Finance|discounted cash flows;discounted cash flow;dcf valuation|10
Residual Income Valuation|T/Finance|discounted residual income;residual income valuation|10
Comparable Valuation Analysis|T/Finance|comparative valuation analysis;comparable valuation;relative valuation|10
Credit Analysis|T/Finance|credit analysis;credit risk;credit risk scores;default rates|10,73
Profitability Analysis|T/Finance|measure profitability;loan profitability;profitability analysis;determinants of the profitability|10,73,223
Investment Analysis|T/Finance|investment analysis;investment decision;investment potential;investments|10,98,113,122
Portfolio Management|T/Finance|portfolio management;management of a student managed portfolio;portfolio strategies;management of investment alternatives;asset management|98,112,113,115,116
Portfolio Diversification|T/Finance|portfolio diversification;diversification of investments|98
Asset Allocation|T/Finance|asset allocation;allocation of investment assets|98
Investment Performance Evaluation|T/Finance|performance evaluation;portfolio performance;investment performance evaluation|98
Fixed Income Analysis|T/Finance|fixed income assets;bond market;bond markets;valuing stocks and bonds|98,101,113@bond,117
Equity Analysis|T/Finance|equity assets;equity research;stock market;stock markets|98,112,113@stock,117
Mutual Fund Analysis|T/Finance|mutual funds;mutual fund analysis|98
Small Business Finance|T/Finance|small business finance;financing for a small business;financial management of small businesses|99
Business Planning|T/Finance|business plan;business planning|99
Break-Even Analysis|T/Finance|break-even analysis;breakeven analysis;break even analysis|99
Working Capital Management|T/Finance|working capital management;short-term financial planning|99,101
Real Estate Valuation|T/Finance|real estate evaluation;real estate valuation;property valuation|100
Real Estate Finance|T/Finance|real estate finance;real estate financing;real estate evaluation and financing|100,122
Real Estate Investment Analysis|T/Finance|investment analysis of real estate;real estate investment;real estate finance and investment|122
Time Value of Money|T/Finance|time value of money;tvm|101
Capital Budgeting|T/Finance|capital budgeting;capital investment appraisal|101,109
Financial Planning|T/Finance|financial planning;financial planning models|101,109
International Finance|T/Finance|international finance;international financial markets;financial management of the multinational firm|101,110,111
Financial Modeling|T/Finance|financial modeling;financial modelling;financial planning models|106,109
Bloomberg|T/Finance|bloomberg;bloomberg terminal;bloomberg certification|107
Capital Structure Analysis|T/Finance|capital structure;recapitalization;financial leverage|73,108,109
Corporate Restructuring|T/Finance|reorganization;recapitalization;corporate restructuring|108
Risk-Return Analysis|T/Finance|risk/return tradeoffs;risk-return tradeoff;risk and return|109
Investment Banking|T/Finance|investment banking;investment bank|112
Private Equity|T/Finance|private equity;pe investing|112,120
Venture Capital|T/Finance|venture capital;vc investing|120,123
Financial Risk Management|T/Finance|financial risk;manage risk using derivative securities;hedge risks|114,119
Derivatives|T/Finance|derivative securities;derivatives;derivative contracts|114
Options|T/Finance|options;futures-options;option contracts|43,114
Swaps|T/Finance|swaps;swap contracts|114
Futures|T/Finance|futures;futures contracts;futures market|43,114
Forward Contracts|T/Finance|forward contracts;forward agreements|114
Hedging|T/Finance|hedging;hedge risks;risk hedging|43,119
Financial Market Analysis|T/Finance|financial markets;capital markets;securities markets;financial market|45,73,110,117,119
Financial Technology|T/Finance|financial technology;fintech|118
ESG Investing|T/Finance|esg;environmental, social and governance;environmental, social, and governance;esg investing|118,128
Financial Regulation|T/Finance|bank resolution;financial regulation;fair credit lending acts|73,118
Financial Institution Management|T/Finance|financial institution management;financial intermediaries;financial institutions|119
Deal Evaluation|T/Finance|deal evaluation;investment deal evaluation|120
Deal Structuring|T/Finance|deal structuring;transaction structuring|120
Due Diligence|T/Finance|due diligence;investment due diligence|120
Investment Fund Structuring|T/Finance|fund structures;fund structuring;investment fund structure|120
Value Creation Strategy|T/Finance|value creation strategies;value creation strategy|120
Cost of Capital Analysis|T/Finance|cost of capital analysis;cost of capital;wacc|121
Portfolio Optimization|T/Finance|portfolio optimization;portfolio optimisation|121
Impact Investing|T/Finance|impact investing;social impact investing|128
Microfinance|T/Finance|microfinance;microfinancing|128
Microeconomic Analysis|T/Economics|microeconomic analysis;microeconomics;microeconomic theory;microeconomic foundations;microeconomic models|37,38,54,63,66,71,83,86,88
Macroeconomic Analysis|T/Economics|macroeconomic analysis;macroeconomics;macroeconomy;macro-economy;macroeconomic performance|46,47,48
Opportunity Cost Analysis|T/Economics|opportunity cost;opportunity costs|32
Marginal Analysis|T/Economics|marginal analysis;marginal economic analysis|32
Supply and Demand Analysis|T/Economics|supply and demand;labor supply and demand;supply-demand analysis|32,91
Game Theory|T/Economics|game theory;strategic interaction;games and decisions|32,49,76,86,169,174
Economic Growth and Development|T/Economics|economic development;growth theory;economic growth;structure and development|33@why do some societies grow rich,40,53,55,56
Economic History Analysis|T/Economics|economic history;historical development of the economies;historical development of economic thought;historical development of financial and economic institutions|40,41,42,45,72
Industrial Organization|T/Economics|industrial organization;industrial structure;industrial & antitrust economics;imperfect competition;oligopolistic competition|18,37,66,71,86,88
Economic Policy Analysis|T/Economics|government policy;public policy;public policies;policymaking;policy recommendations|38,39,46@governmental policy,49,52,74@healthcare economics & policy,87,88@design efficient policies,97
Economics of Crime|T/Economics|economics of crime;crime-control policies;costs of crime;crime prevention|39
Sports Economics|T/Economics|economics of sports;sports economics|44
Monetary Policy Analysis|T/Economics|monetary policy;monetary economics;monetary and fiscal variables|48,72,75,117
Fiscal Policy Analysis|T/Economics|fiscal policy;monetary and fiscal variables;governmental revenue and expenditure|48,77,117
Law and Economics|T/Economics|law and economics;economic analysis to analyze the basic common law;law, statistics, and economics|50,79
International Trade Analysis|T/Economics|international trade;trade restrictions;tariffs;commercial policy|33,52,82
Exchange Rate Analysis|T/Economics|exchange rates;currencies;exchange rate analysis|81,117
Balance of Payments Analysis|T/Economics|balance of payments;balance-of-payments|81
Environmental Economics|T/Economics|environmental economics;economics of the natural environment;economic development and environment|57,89,90
Natural Resource Economics|T/Economics|natural resources;natural resource economics;public land management|90
Energy Market Analysis|T/Economics|energy markets;markets for energy;energy production and consumption|89
Labor Economics|T/Economics|labor economics;labor and the economy;labor supply and demand;wage determination;labor and public policy|58,91,92
Labor Market Discrimination Analysis|T/Economics|labor market discrimination;economic models of discrimination;economic analysis of discrimination|64,91
Experimental Economics|T/Economics|experimental economics;experimental studies of economic behavior;lab experimental|65
Econometrics|T/Economics|econometrics;econometric method;econometric methods;estimating and testing economic models|64,69,85,88
Mathematical Economics|T/Economics|mathematical economics;mathematical structure;mathematical models|70,73
Health Economics|T/Economics|health economics;healthcare economics;health-care sectors|71,74
Public Finance|T/Economics|public finance;public sector economics;governmental revenue and expenditure|71,77
Decision Theory|T/Economics|decision theory;decision analysis;decisions under uncertainty|76,187
Behavioral Economics|T/Economics|behavioral economics;psychological insights;behavioral decision frameworks|78,188
Behavioral Game Theory|T/Economics|behavioral game theory;psychology into the study of economics|80
Economic Damages Estimation|T/Economics|economic damages;quantitative methods to determine appropriate economic damages|79
General Equilibrium Analysis|T/Economics|general equilibrium analysis;general equilibrium|82
Information Economics|T/Economics|information economics;economics of imperfect information|66,83
Antitrust Analysis|T/Economics|antitrust policies;antitrust economics;antitrust analysis|86
Regulatory Economics|T/Economics|regulated industries;regulated sector;regulation is appropriate|87,88
Climate Economics|T/Economics|economics of climate change;economic approaches to managing climate change;climate science and economics|90,97
Climate Modeling|T/Economics|climate modeling;climate modelling|97
Economic Modeling|T/Economics|economic modeling;economic modelling;economic models;microeconomic models|64,69,88,97
Statistical Inference|T/Statistics|statistical inference;data analysis and inference;applied statistics|30
Statistical Analysis|T/Statistics|statistical analysis;statistical measures;economic statistics;statistical tools|30@applied statistics,31,51,85@statistical techniques
Linear Regression|T/Statistics|linear regression;single linear regression;linear regression analysis|31,69@classical regression model,85
Multiple Linear Regression|T/Statistics|multiple linear regression;multiple regression;multivariable linear regression|31
Statistical Model Estimation|T/Statistics|equation estimation;estimating and testing economic models;model estimation|69
Regression Diagnostics|T/Statistics|regression model assumptions;regression diagnostics;violating classical regression|69
Nonparametric Statistics|T/Statistics|non-parametric statistics;nonparametric statistics;nonparametric methods|78
Panel Data Modeling|T/Statistics|panel data models;panel data modeling;panel regression|85
Logistic Regression|T/Statistics|logistic regression;logit regression|85
Decision Trees|T/Statistics|classification and regression trees;decision trees;cart|85
Analysis of Variance|T/Statistics|analysis of variance;anova|85
Statistical Programming|T/Statistics|statistical programming;programming for statistics|85
SAS|T/Statistics|sas;statistical analysis system|85
Data Analysis|T/Analytics|data analysis;data analytics;analysis of data;analyzing data|30,31@analysis of real business datasets,84,85,212,224
Business Analytics|T/Analytics|business analytics;business intelligence and analytics;analytical modeling;quantitative analyses|31,212
Data Management|T/Analytics|data management;data handling;manage very large data sets|31,85
Data Cleaning|T/Analytics|data cleaning;cleaning;data cleansing|31,85
Data Integration|T/Analytics|merging;data integration;data merging|85
Data Preparation|T/Analytics|preparation of large datasets;data preparation;data preprocessing|85
Data Collection|T/Research|data collection;collection of data;gathering and analyzing data;assembly, interpretation and use of economic data|84,150,207,224
Data Visualization|T/Analytics|data visualization;graphic visualization;visualization techniques;charts|31,85,212,236
Microsoft Excel|T/Analytics|excel;microsoft excel;excel spreadsheets;spreadsheet|31,101,104,106,109,236,240
Tableau|T/Analytics|tableau;tableau software|31
Big Data Analytics|T/Analytics|big data analytics;big economic and business datasets;large data sets;large datasets|31,85,212
Forecasting|T/Analytics|forecasting;forecasts;revenue forecasts;sales forecasts|10,69,84,99,180,237
Data Mining|T/Analytics|data mining;data mining methods|212
Web Mining|T/Analytics|web mining;web mining techniques|212
Business Intelligence|T/Analytics|business intelligence;bi analytics|212
Business Modeling and Simulation|T/Analytics|business modeling and simulation;laboratory simulations;business simulation|173,214
Optimization Modeling|T/Analytics|optimization methods;optimization and decision support modeling;optimization modeling|236,240
Linear Programming|T/Analytics|linear programming;linear optimization|236@linear,240@linear
Integer Programming|T/Analytics|integer programming;integer optimization|236@integer,240@integer
Nonlinear Programming|T/Analytics|nonlinear programming;nonlinear optimization|236@linear,240@linear
Network Optimization Models|T/Analytics|network models;network optimization;network flow models|236,240
Monte Carlo Simulation|T/Analytics|monte carlo simulation;monte carlo methods|236,240
Decision Support Systems|T/Information Systems|decision support systems;decision support methods;decision support modeling|204,236,240
Spreadsheet Modeling|T/Analytics|spreadsheet modeling;model them on excel spreadsheets;use of a spreadsheet;applied excel modeling|106,109,236,240
Excel Functions|T/Analytics|built-in functions;excel functions;spreadsheet functions|236,240
Excel Named Ranges|T/Analytics|named ranges;excel named ranges|236,240
Pivot Tables|T/Analytics|pivot tables;pivottables|236,240
Conditional Formatting|T/Analytics|conditional formatting;excel conditional formatting|236,240
Excel Macros|T/Analytics|macros;excel macros;spreadsheet macros|236,240
Programming|T/Programming|programming;software development;development of software tools;build automated financial applications|85,121,200@java implementations,210
Java|T/Programming|java;java programming|200
C Programming|T/Programming|c programming;tutorial in c;c language|200
Data Structures|T/Programming|data structures;stacks;queues;trees and graphs|200
Algorithm Design and Analysis|T/Programming|algorithms;algorithm design;algorithms for searching;sorting;graph traversal|200
Software Engineering|T/Programming|software engineering;software systems engineering|204
AI Literacy|T/AI|ai literacy;artificial intelligence;ai tools|121
AI-Assisted Programming|T/AI|ai-assisted programming;vibe coding;ai assisted programming|121
AI Agent Development|T/AI|custom ai agents;ai agent development;build ai agents|121
Financial Application Automation|T/AI|automated financial applications;financial application automation|121
Automated Report Generation|T/AI|automated report generation;report automation|121
Deception Detection Software|T/Programming|detection of deception and intent;detect deception;automatic deception|210
Digital Literacy|T/Information Systems|computer technology;understanding of computers;interacting with the internet|199
Information Systems Management|T/Information Systems|managing information systems;management information systems;use of computer technology;information management|175,201,211
Computer Networking|T/Information Systems|data communications;networks;network devices;protocols|202,208
E-Commerce|T/Information Systems|electronic commerce;e-commerce;ecommerce|83,202,212
Database Management|T/Database|database management systems;database management;dbms|203
Relational Database Design|T/Database|relational databases;relational models;relational database design|11,203
Database Security|T/Database|security concurrency;database security|203
Database Concurrency Control|T/Database|concurrency;concurrency control;database concurrency|203
Database Integrity|T/Database|integrity and recovery;database integrity;data integrity|203
Database Recovery|T/Database|recovery issues;database recovery;database restoration|203
Database Querying|T/Database|query interfaces;database querying;relational query|203
Healthcare Information Systems|T/Information Systems|healthcare information systems;health it;health information systems|204
Human-Computer Interaction|T/Information Systems|human-computer interaction;human computer interaction;hci|204
Technology Acceptance Evaluation|T/Information Systems|user acceptance;outcomes evaluation methods;technology acceptance|204
Information Systems Analysis and Design|T/Information Systems|information systems analysis and design;information systems design;logical system design|204,211
Systems Development Life Cycle|T/Information Systems|systems development life cycle;sdlc;system development life cycle|211
Requirements Analysis|T/Information Systems|information systems requirements;requirements analysis;requirements gathering|211
Business Process Design|T/Information Systems|design of business processes;business process design;process design|211,237
Systems Integration|T/Information Systems|system integration;enterprise integration;systems integration|175,201
Enterprise Resource Planning|T/Information Systems|enterprise resource planning;erp;enterprise computing environments|209
Expert Systems|T/Information Systems|expert systems;expert system|175
Information Security|T/Cybersecurity|information security;infosec;confidentiality, availability, and integrity;cyber security|206,207,208
Network Security|T/Cybersecurity|network security;secure information;network protection|206,208
Systems Security Administration|T/Cybersecurity|systems security management;safeguarding operating systems;system administrators|208
Information Security Risk Assessment|T/Cybersecurity|risk assessment;information security risk management;security risks|207,208
Security Threat Analysis|T/Cybersecurity|security threats;threat analysis;security threat analysis|206@threats,210
Security Countermeasures|T/Cybersecurity|security countermeasures;mitigation of security risks;security mitigation|206@countermeasures,208
Operations Security|T/Cybersecurity|opsec;operations security|206
Information Assurance|T/Cybersecurity|information assurance;assurance of information security|208
Data Privacy|T/Cybersecurity|privacy;data privacy;information privacy|175
Risk Reporting and Monitoring|T/Cybersecurity|risk reporting and monitoring;risk reporting;risk monitoring|207
Marketing Management|T/Marketing|marketing management;marketing concepts;marketing policies and operations;marketing operations|25,217,228,231@topics in the field of marketing,232
Marketing Strategy and Planning|T/Marketing|marketing strategy;marketing plans;marketing planning;marketing programming and strategy|142,186,216,219
Consumer Behavior Analysis|T/Marketing|consumer behavior;customer behavior;consumer behaviour|25,219,225
Sports Marketing|T/Marketing|sports marketing;sports teams;marketing activities|142,216
Marketing Analytics|T/Marketing|marketing analytics;marketing and financial metrics;effectiveness of different digital marketing tactics|218,219
Digital Marketing|T/Marketing|digital marketing;digital marketing strategy|219
Search Marketing|T/Marketing|search marketing;search engine marketing;sem|219
Social Media Marketing|T/Marketing|social media;social media marketing;social marketing channels|219
Customer-Friendly Website Design|T/Marketing|customer-friendly website;customer friendly website;customer-focused website design|219
Advertising|T/Marketing|advertising;advertising communications|220,226
Advertising Message Development|T/Marketing|message creation;advertising message;advertising communications|220
Media Planning and Selection|T/Marketing|media selection;media planning;media selection model|220,236
Marketing Performance Measurement|T/Marketing|measurement of results;marketing and financial metrics;effectiveness of different digital marketing tactics|218,219,220
Pricing Strategy|T/Marketing|pricing strategy;pricing decisions;pricing & channels|221
Channel and Distribution Management|T/Marketing|marketing channels;distribution systems;managing marketing channels;channel conflict|221
Sales|T/Marketing|selling skills;sales communications;interpersonal marketing communications|222
Customer Relationship Management|T/Marketing|customer relationship management;crm|222
Retail Marketing|T/Marketing|retail marketing;retail enterprises;retail strategy|223
Competitive Analysis|T/Marketing|competitive analysis;competitive strategy;strategy and competition|181,223
Market Selection|T/Marketing|market selection;market identification;target market selection|220,223
Retail Location Planning|T/Marketing|retail location;retail site selection|223
Merchandise Planning and Control|T/Marketing|merchandise budgeting and control;merchandise planning;merchandise management|223
Store Layout and Design|T/Marketing|store layout and design;retail store design|223
Marketing Research|T/Marketing|marketing research;research for marketing decisions;market research|224,233
Integrated Marketing Communications|T/Marketing|integrated marketing communications;promotion mix;imc|226
Public Relations|T/Marketing|public relations;pr communications|226
Sales Promotion|T/Marketing|sales promotions;sales promotion;promotional campaigns|226
Sales Operations Management|T/Marketing|sales operations;sales organizations;sales strategies|172,227
International Marketing|T/Marketing|international marketing;international marketer;marketing operations for foreign environments|228
Healthcare Marketing|T/Marketing|health care marketing;healthcare marketing;public health marketing|229
Product Innovation|T/Marketing|product innovation;new product development;generating ideas|186,230,233
Product Strategy|T/Marketing|product (services) strategy;product strategy;product and services strategy|230
Product Launch|T/Marketing|launching new offerings;product launch;new product launch|230
Product Portfolio Management|T/Marketing|product (services) portfolio;product portfolio;service portfolio|230
Marketing Operations Auditing|T/Marketing|auditing of marketing organizations;marketing auditing;marketing operations|232
Operations Management|T/Operations|operations management;production operations;productive systems|165@operations,180,181,237
Service Operations Management|T/Operations|service operations;service systems;service type industries|180,238,242
Supply Chain Management|T/Operations|supply chain management;supply chain;supply chains|181,183,239,243
Logistics|T/Operations|logistics;logistical strategies;material flow processes|183,236,239,243
Procurement|T/Operations|procurement;purchasing;sourcing|183,239,243
Materials Handling|T/Operations|handling;materials handling;material handling|183,239,243
Warehousing|T/Operations|warehousing;warehouse management;warehouse operations|183,239,243
Transportation Management|T/Operations|transportation;transportation management;transport logistics|183,236,239,243
Inventory Management|T/Operations|inventory control;inventory models;inventory management|180,183,239,243
Aggregate Planning|T/Operations|aggregate planning;aggregate sales and operations planning;sales and operations planning;s&op|180,237,241
Materials Requirements Planning|T/Operations|mrp;materials resource planning;material requirements planning;materials requirements planning|180,237,241
Production Scheduling|T/Operations|production scheduling;scheduling;production planning|180,237,241
Facility Layout and Location|T/Operations|facilities layout and location;facility layout;facility location|181
Quality Management|T/Operations|quality management;quality improvement;quality and assurance;lean/quality principles|177,181,237
Statistical Process Control|T/Operations|statistical process control;spc|177
Reliability and Maintainability|T/Operations|reliability and maintainability;reliability engineering;maintainability|181
Manufacturing Product Design|T/Operations|product design for manufacturing;design for manufacturing;dfm|237,241
Capacity Management|T/Operations|capacity management;capacity planning|237,241
Lean Operations|T/Operations|lean/quality principles;lean operations;lean manufacturing|237,241
Resource Allocation|T/Operations|resource allocation;allocate resources;allocation of resources|38,77,236
Revenue Management|T/Operations|revenue management;revenue optimization|236,240
Outsourcing Analysis|T/Operations|outsourcing production;outsourcing analysis;production outsourcing|236,240
Project Management|T/Management|project management;project activities;project requirements|181,211,213
Project Scope Management|T/Management|project scope;scope management|213@scope
Project Cost Management|T/Management|project cost;project budget management;project cost management|213@cost
Project Schedule Management|T/Management|scheduling software;project schedule;project scheduling|213
Project Quality Management|T/Management|project quality;project quality management|213@quality
Cost-Benefit Analysis|T/Management|cost-benefit analysis;cost benefit analysis;benefit-cost analysis|211
Risk Management|T/Management|risk management;risk assessment;risk mitigation|99,206,207
Decision Making Under Uncertainty|T/Analytics|decision making under uncertainty/risk;decisions under uncertainty;uncertainty/risk|236,240
Organizational Behavior|T/Management|organizational behavior;organization behavior;group functioning|24,134,168,182
Human Resource Management|T/HR|human resource management;human resources management;hr management;hrm|136,158,161
Strategic Human Resource Management|T/HR|strategic human resource management;people management practices;organization's strategy and structure|161
Compensation and Benefits|T/HR|compensation;compensation and benefits;compensation policies|155,157,175
Recruiting and Staffing|T/HR|organizational staffing;staff positions;pool of applicants;procurement, development, compensation|157,164
Employee Training and Development|T/HR|training and development;employee competence;developing people|161,171
Performance Management|T/HR|performance management;employee performance management|175
Human Resource Information Systems|T/HR|human resource information systems;hris;human resources information systems|175
Human Resource Planning|T/HR|human resource planning;workforce planning|175
Labor Relations|T/HR|labor relations;industrial relations;labor and management|58,175
Equal Employment Opportunity|T/HR|equal employment opportunity;affirmative action;eeo;comparable worth|175,185
Employee Motivation|P/Leadership|motivating;motivation of personnel;motivate people;motivate an employee|135,137,157,166,178
Strategic Management|T/Management|strategic management;strategic planning;corporate strategy;economic strategy|63,111,147,179,223
Organization Design|T/Management|organization design;designing and managing organizations;organization theory;organization's strategy and structure|161,165,167
Organizational Change Management|T/Management|organizational change;diagnose, design, manage, change;change management|201,167
International Business|T/Management|international business;global business;globalizing business;international integration|18,20,28,29,163,176
Management Consulting|T/Management|management consulting;consulting industry;applied consulting;nonprofit consulting|21,148,194
Client Management|P/Collaboration|client management;client relationship management|148
Nonprofit Management|T/Management|non-profit organizations;nonprofit organizations;governing and leading;nonprofit management|146@nonprofit,147,148
Organizational Governance|T/Management|governing and leading;organizational governance;nonprofit governance|147
Volunteer Management|T/Management|managing staff and volunteers;volunteer management|147
Fundraising|T/Management|fundraising;fund raising;fund-raising|147
Social Innovation|T/Management|social innovation;social impact cycle;creating social impact|146
Entrepreneurship|T/Management|entrepreneurship;entrepreneurial skills;entrepreneurial initiatives;new ventures|40,123,133,170,189
Social Entrepreneurship|T/Management|social entrepreneurship;social and/or environmental problem solving|189
Healthcare Entrepreneurship|T/Management|healthcare entrepreneurship;entrepreneurial solutions;health care entrepreneurship|170
Healthcare Management|T/Management|health care organization and management;health care delivery;health care organizations;healthcare management|162,165
Sports Administration|T/Management|sports administration;sports management;sports programs;athletics departments|138,141,144@sports organizations,145
Event Management|T/Management|event management;sport tourism;events / tournaments|139
Sports Facility Operations|T/Management|operating sports facilities;sports facilities;sports facility operations|138
Sports Regulatory Compliance|T/Law & Policy|sports negotiation and compliance;ncaa requirements;compliance at the college and professional levels|140,141
Business Law|T/Law & Policy|business law;legal considerations;law and ethics in the workplace|24,154,156
Contract Law|T/Law & Policy|law of contracts;contract;contract law|50,156
Agency Law|T/Law & Policy|principal-agency;employer-employee;agency law|156
Business Entity Law|T/Law & Policy|business associations;limited partnerships;limited liability companies;corporations|156
Property Rights Law|T/Law & Policy|property rights;property law;legal concepts|90,100,156
Negotiable Instruments|T/Law & Policy|negotiable instruments;negotiable instrument law|156
Estate and Probate Law|T/Law & Policy|wills and probate;probate of estate;estate law|156
Legislative Analysis|T/Law & Policy|summarizing legislative proposals;legislative analysis;legislative proposals|192
Research|T/Research|research;research methodologies;scholarly information;research-based writing|13,15,60,93,127,148,151,185,193,214,215,235
Experimental Research|T/Research|experimental research;experiments;experimental studies;laboratory simulation|65,78,169@experimental findings,173,174
Research Problem Definition|T/Research|problem definition;determination of information needs;research question formulation|224
Information Literacy|P/Thinking|information literacy;sources of investing information;information needs|98,223,224
Business Communication|P/Communication|business communication;communication strategies;professional communication|14,15@communication practices professionals rely on in business settings,17,143
Written Communication|P/Communication|written communication;write clearly;writing;written report;written and oral reports|15,16,143@written business communication,173,192
Oral Communication|P/Communication|oral;spoken;oral communication;verbal communication|15,16,143,192
Presentation Skills|P/Communication|presentations;present ideas;presentation of findings;presenting|15,151,224
Visual Communication|P/Communication|visual communication;visual messaging|15@visual
Data Communication|P/Communication|data-driven messaging;communicate their findings;communicate their results;presentation of findings|15,31,85,224
Audience Analysis|P/Communication|business audiences;stakeholder expectations;professional audiences;technical and non-technical audience|15,17,85
Persuasion|P/Communication|persuasion;persuasively;persuasive communication|15,178,222
English Grammar and Vocabulary|P/Communication|grammar skills;vocabulary building;english written/oral organizational skills|16
English Pronunciation|P/Communication|pronunciation/intonation;pronunciation;intonation|16
Research and Academic Writing|P/Communication|honors thesis;reports, and/or papers;research-based writing;term paper|13,15,60,93,127,193,196,214,215,235,243
Teamwork and Collaboration|P/Collaboration|collaborate effectively;working with others;work in teams;managing groups and teams;group project|15,135,148,168,204,219
Negotiation|P/Collaboration|negotiation;negotiations;bargaining;negotiate|140,159,160,186,222
Conflict Management|P/Collaboration|deal with conflict;conflict and cooperation;conflict management;conflict resolution|135,174
Cross-Cultural Competence|P/Cross-Cultural|across cultures;cultural norms;comparative cultural practices;cultural grounding and competency;global/cultural awareness|15,16,20,176,223
Leadership|P/Leadership|leadership;leading;leaders effective;leader effectiveness|15,135,137,166,184,185
People Management|P/Leadership|manage people;managing and developing people;people management;managing staff|147,161
Team Management|P/Leadership|managing groups and teams;group functioning;team management|168
Critical Thinking|P/Thinking|critical thinking;critically;critical opinions;critical survey;analysis, synthesis, and evaluation;higher-order thinking|17,64,118,121,167,169,199,201@critical analysis
Analytical Thinking|P/Thinking|analytical skills;analytic;analysis, synthesis, and evaluation;analytical and communication skills|17,31,106,163
Problem Solving|P/Thinking|problem solving;problem-solving;solve practical finance problems;solving managerial decision problems|19,30,106,109,236
Decision Making|P/Thinking|decision making;decision-making;effective decisions;decision maker|1,3,19,135,187,188
Ethical Reasoning|P/Ethics|ethical;ethics;moral reasoning;moral and ethical dilemmas|9,24,33,129,154,199,204,205
Career Planning and Management|P/Career|career management;career planning;career decision-making;career choice|19,185
Self-Assessment|P/Career|self-assessment;self assessment;assessment of values, interests, and skills|19
Professional Networking|P/Career|networking;business relationships;professional networking|20,21@network,112
Self-Directed Learning|P/Career|self-directed;responsible for their own knowledge acquisition;self directed learning|16
Security Asset Valuation|T/Cybersecurity|asset valuation;security asset valuation;valuation of information assets|207
Market Efficiency Analysis|T/Finance|market efficiency;efficient markets;market efficiency analysis|98
Hypothesis Testing for Economic Models|T/Statistics|testing economic models;statistical hypothesis testing;hypothesis testing|69
Economic Welfare Analysis|T/Economics|economic outcomes and welfare;social welfare;welfare aspects;consumer and producer welfare|38,49,82,88
Climate Science Fundamentals|T/Economics|fundamentals of climate change;climate science;climate change fundamentals|97
Tort Law|T/Law & Policy|tort;tort law|50
Criminal Law|T/Law & Policy|criminal law;criminal legal analysis|50
Operations Strategy|T/Operations|operations strategy;strategy and competition|181,237,241
HR Systems Selection and Evaluation|T/HR|selection and evaluation of an appropriate hris;hr systems selection;hris evaluation|175
Workplace Diversity Analysis|T/HR|gender and organizations;occupational sex segregation;labor market discrimination;workplace diversity|64@race,91,185
Business Opportunity Evaluation|T/Management|evaluating opportunities;healthcare challenges and opportunities;business opportunity evaluation|170,230
Economic Analysis|T/Economics|economic analysis;economics analysis;economic perspective|32@economists,67,68,96
'''


def read_source():
    expected_hash = '21c85dcabc2a956268a4b5283c3cc976b722684df34e0bb447fd37dea799a302'
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Source CSV changed. Review source-row references before regenerating.')
    with SOURCE.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def excerpt(course, aliases, anchor=None):
    """Find a supporting literal alias, retaining source wording and qualifiers."""
    for field in ('Course Description', 'Course Title'):
        text = course[field]
        for alias in ([anchor] if anchor else aliases):
            pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
            match = re.search(pattern, text, re.I)
            if match:
                # A generous window preserves context; full short descriptions stay intact.
                start = max(0, match.start() - 160)
                stop = min(len(text), match.end() + 300)
                return field, text[start:stop], alias
    raise ValueError(f'No supporting alias in {course["Subject code"]} {course["Catalog Number"]}: {aliases}')


def write_csv(name, headers, rows):
    with (BASE / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main():
    courses = read_source()
    skills, evidence = [], []
    seen = set()
    for line in DEFINITIONS.strip().splitlines():
        name, category_code, aliases_text, indexes_text = line.split('|')
        assert name.casefold() not in seen, name
        seen.add(name.casefold())
        prefix, suffix = category_code.split('/')
        category = ('Technical' if prefix == 'T' else 'Professional') + ' / ' + suffix
        aliases = list(dict.fromkeys([name.lower(), *aliases_text.lower().split(';')]))
        skill_id = f'SK_{len(skills) + 1:03d}'
        assert len(skill_id) <= 16 and len(name) <= 64 and len(category) <= 32, (name, category)
        skills.append(dict(skill_id=skill_id, skill_name=name, skill_category=category,
                           search_synonyms=json.dumps(aliases, ensure_ascii=False)))
        for source_ref in indexes_text.split(','):
            index_text, _, anchor = source_ref.partition('@')
            course = courses[int(index_text)]
            field, quote, matched = excerpt(course, aliases, anchor or None)
            evidence.append(dict(skill_id=skill_id, source_csv_row=int(index_text) + 2, course_id=course['Course ID'],
                subject_code=course['Subject code'], catalog_number=course['Catalog Number'],
                course_title=course['Course Title'], source_field=field,
                evidence_term=matched, evidence_excerpt=quote))
    write_csv('course_skills.csv', ['skill_id', 'skill_name', 'skill_category', 'search_synonyms'], skills)
    write_csv('skill_course_evidence.csv', ['skill_id', 'source_csv_row', 'course_id', 'subject_code', 'catalog_number',
              'course_title', 'source_field', 'evidence_term', 'evidence_excerpt'], evidence)
    schema = [
        {'Column Name':'skill_id (PK)', 'Data Type':'VARCHAR(16)', 'Example Row Value':'"SK_001"', 'Purpose in Analysis':'Canonical ID used across Tables 3 and 4'},
        {'Column Name':'skill_name', 'Data Type':'VARCHAR(64)', 'Example Row Value':'"SQL"', 'Purpose in Analysis':'Clean display name'},
        {'Column Name':'skill_category', 'Data Type':'VARCHAR(32)', 'Example Row Value':'"Technical / Database"', 'Purpose in Analysis':'Groups skills into Technical vs. Professional/Soft'},
        {'Column Name':'search_synonyms', 'Data Type':'ARRAY<STR>', 'Example Row Value':'["sql", "postgresql", "t-sql", "mysql", "relational query"]', 'Purpose in Analysis':'Regex/keyword lookup list for text extraction'},
    ]
    write_csv('skills_schema.csv', ['Column Name', 'Data Type', 'Example Row Value', 'Purpose in Analysis'], schema)
    counts = Counter(s['skill_category'].split(' / ')[0] for s in skills)
    summary = dict(source=str(SOURCE.relative_to(BASE.parent)), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   course_rows_reviewed=len(courses), unique_skills=len(skills), category_counts=dict(counts),
                   supporting_excerpts=len(evidence), source_rows_with_representative_evidence=len({e['source_csv_row'] for e in evidence}))
    (BASE / 'extraction_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
