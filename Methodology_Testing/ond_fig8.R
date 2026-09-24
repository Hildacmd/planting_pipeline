d<-readRDS("/tmp/ond_profiles.rds"); val<-d$val; P<-d$P
rd<-readRDS("/tmp/raindays.rds"); stopifnot(identical(rd$county,val$county))
dk<-rd$dekads; ix<-function(a,b) which(dk>=a & dk<=b)
OUT<-"Methodology_Testing/figs"
C_E<-"#1B72B8"; C_L<-"#C1471E"; GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"
E<-val$survey_ond_regime=="early (Aug-Sep)"; C<-val$chirps_rain_structure=="continuous (no dry break)"
au<-function(x,g){a<-x[g];b<-x[!g];m<-mean(outer(a,b,">")+0.5*outer(a,b,"=="));max(m,1-m)}
pv<-function(x,g) suppressWarnings(wilcox.test(x[g],x[!g]))$p.value
# Only the SURVEY split is a non-circular test: the CHIRPS split is DEFINED by Aug-Sep rainfall<100mm,
# so any Aug-Sep rainfall variable separates it by construction. Scored against the survey split only.
V<-list("Aug-Sep rainfall total (mm)"=rowSums(P[,22:27]),
        "Aug-Sep rain days >= 1 mm"=rowSums(rd$rd1[,ix(22,27)]),
        "Aug-Sep rain days >= 10 mm"=rowSums(rd$rd10[,ix(22,27)]),
        "Jul-Dec rain days >= 1 mm"=rowSums(rd$rd1),
        "Oct-Nov rainfall total (mm)"=rowSums(P[,28:33]),
        "Oct-Nov rain days >= 1 mm"=rowSums(rd$rd1[,ix(28,33)]))
nm<-names(V); n<-length(nm)
png(file.path(OUT,"ond_split_fig8_raindays.png"),1720,830,res=150)
layout(matrix(1:2,1,2),widths=c(1.12,1))
par(mar=c(5.8,14.8,5.6,5.4),oma=c(0,0,3.4,0),xpd=FALSE)
plot(NA,xlim=c(.5,.95),ylim=c(.4,n+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(.5,.9,.1),col=GRID,lwd=1)
for(i in 1:n){y<-n-i+1; x<-V[[i]]; a<-au(x,E); p<-pv(x,E)
  cl<-if(p<0.05) C_L else "#A9A296"
  segments(.5,y,a,y,col=cl,lwd=11,lend=1)
  text(a+.008,y,sprintf("%.2f  p=%.3f",a,p),adj=0,cex=.68,col=cl,font=2,xpd=NA)}
axis(2,at=n:1,labels=nm,las=1,col=GRID,col.axis=INK,cex.axis=.78,tck=-.012)
axis(1,at=seq(.5,.9,.1),col=GRID,col.axis=MUT,cex.axis=.76,tck=-.02)
mtext("A. Separating power against the survey split",3,line=1.9,adj=0,cex=.98,font=2,col=INK)
mtext("AUC (0.50 = none). Survey labels only — see note",3,line=.7,adj=0,cex=.74,col=MUT)

par(mar=c(5.8,6.0,5.6,2.0))
x<-rowSums(rd$rd10[,ix(22,27)])
plot(NA,xlim=c(.5,2.5),ylim=c(-.8,max(x)*1.20),axes=FALSE,xlab="",ylab="")
abline(h=pretty(c(0,max(x))),col=GRID,lwd=1)
for(j in 1:2){cl<-if(j==1)C_E else C_L; v<-x[if(j==1)C else !C]
  rect(j-.26,quantile(v,.25),j+.26,quantile(v,.75),col=paste0(cl,"33"),border=cl,lwd=1.8)
  segments(j-.26,median(v),j+.26,median(v),col=cl,lwd=3)
  points(jitter(rep(j,length(v)),amount=.11),v,pch=19,col=paste0(cl,"BB"),cex=.95)}
axis(1,at=1:2,labels=c("continuous\n(no dry break)","distinct OND\n(dry break)"),col=GRID,col.axis=MUT,cex.axis=.82,tck=-.02,padj=.55)
axis(2,las=1,col=GRID,col.axis=MUT,cex.axis=.78,tck=-.02)
mtext("B. What the dry break looks like in rain days",3,line=1.9,adj=0,cex=.98,font=2,col=INK)
mtext("days >= 10 mm across the 61-day Aug-Sep window — descriptive",3,line=.7,adj=0,cex=.74,col=MUT)
mtext("days",2,line=3.5,cex=.80,col=MUT)
text(1.5,max(x)*1.14,"median 7.5 days vs 0.1 days",cex=.80,col=INK,font=2)
par(xpd=NA)
mtext("Rain days: a physical picture of the split, but no better as a discriminator than totals",3,
  outer=TRUE,line=.8,adj=.015,cex=1.13,font=2,col=INK)
dev.off(); cat("ok\n")
