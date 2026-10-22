"""Offline Rekognition planning arithmetic, not a full AWS bill or spending cap."""
import argparse,json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--employees',type=int,default=100);p.add_argument('--days',type=int,default=30);p.add_argument('--captures-per-day',type=int,default=2)
p.add_argument('--group1-rate',type=float,default=.001);p.add_argument('--group2-rate',type=float,default=.001);p.add_argument('--vector-month-rate',type=float,default=.00001)
a=p.parse_args()
if min(a.employees,a.days,a.captures_per_day,a.group1_rate,a.group2_rate,a.vector_month_rate)<0:p.error('Inputs must be nonnegative.')
captures=a.employees*a.days*a.captures_per_day
recurring=captures*(a.group1_rate+a.group2_rate)+a.employees*a.vector_month_rate
enrollment=a.employees*(2*a.group1_rate+a.group2_rate)
print(json.dumps({'attendance_captures':captures,'attendance_analysis_operations':2*captures,'recurring_rekognition_usd':round(recurring,6),
 'initial_enrollment_usd':round(enrollment,6),'first_month_rekognition_usd':round(recurring+enrollment,6),
 'excludes':'Other AWS services, retakes/retries, taxes, credits and discounts'},indent=2))
