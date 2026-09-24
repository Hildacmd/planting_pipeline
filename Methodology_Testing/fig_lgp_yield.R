source("Methodology_Testing/theme.R")
CY<-"Cropyield-Data"
a<-read.csv(file.path(CY,"lgp_ab_arm_summary.csv"),stringsAsFactors=FALSE)
sd_<-read.csv(file.path(CY,"lgp_ab_seed_mae.csv"),stringsAsFactors=FALSE)
LAB<-c("A  fixed 120d, single Ym"="fixed 120 d cycle","B1 zone-aware LGP, single Ym"="zone-aware LGP as cycle",
       "B2 fixed 120d, per-zone Ym"="fixed cycle + per-zone Ym")
CO <-c("A  fixed 120d, single Ym"="#9A9287","B1 zone-aware LGP, single Ym"=PAL[["two"]],
       "B2 fixed 120d, per-zone Ym"=PAL[["e"]])
a$lab<-LAB[a$arm]; a$col<-CO[a$arm]
PX("Methodology_Testing/figs/lgp_yield_skill.png",2100,880)
layout(matrix(1:3,1,3),widths=c(1.02,.92,1.16))
par(mar=c(6.6,12.2,5.8,3.2),oma=c(.4,0,3.6,.4),xpd=FALSE)
## A - LOO MAE
o<-c(2,1,3)   # LGP arm first so the loser reads first
plot(NA,xlim=c(0,.80),ylim=c(.4,3.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,.8,.2),col=GRID,lwd=1)
for(r in 1:3){i<-o[r]; y<-4-r
  rect(0,y-.26,a$loo_mae[i],y+.26,col=paste0(a$col[i],"38"),border=NA)
  segments(0,y,a$loo_mae[i],y,col=a$col[i],lwd=4,lend=1)
  text(a$loo_mae[i]+.014,y,sprintf("%.3f",a$loo_mae[i]),adj=0,cex=.82,col=a$col[i],font=2)}
gridy(3:1,a$lab[o],cex=.86)
gridx(seq(0,.8,.2),cex=.80,line=3.2,title="leave-one-out MAE (t/ha)   lower is better")
ttl("A. Yield skill","n = 46 counties, Kenya long rains")
## B - rank skill
par(mar=c(6.6,3.0,5.8,3.2))
plot(NA,xlim=c(0,.95),ylim=c(.4,3.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,.9,.3),col=GRID,lwd=1)
for(r in 1:3){i<-o[r]; y<-4-r
  rect(0,y-.26,a$spearman[i],y+.26,col=paste0(a$col[i],"38"),border=NA)
  segments(0,y,a$spearman[i],y,col=a$col[i],lwd=4,lend=1)
  text(a$spearman[i]+.016,y,sprintf("%.2f",a$spearman[i]),adj=0,cex=.82,col=a$col[i],font=2)}
gridx(seq(0,.9,.3),cex=.80,line=3.2,title="Spearman rank correlation   higher is better")
ttl("B. Rank skill","does it order the counties correctly?")
## C - 500-seed distribution
par(mar=c(6.6,5.4,5.8,2.4))
A<-sd_$mae[sd_$arm=="A  fixed 120d, single Ym"]; B<-sd_$mae[sd_$arm=="B1 zone-aware LGP, single Ym"]
br<-seq(min(A,B)-.02,max(A,B)+.02,length.out=34)
hA<-hist(A,breaks=br,plot=FALSE); hB<-hist(B,breaks=br,plot=FALSE)
yl<-c(0,max(hA$counts,hB$counts)*1.52)
plot(NA,xlim=range(br),ylim=yl,axes=FALSE,xlab="",ylab="")
abline(h=pretty(yl,4),col=GRID,lwd=1)
for(h in list(list(hA,"#9A9287"),list(hB,PAL[["two"]])))
  rect(h[[1]]$breaks[-length(h[[1]]$breaks)],0,h[[1]]$breaks[-1],h[[1]]$counts,
       col=paste0(h[[2]],"66"),border=NA)
abline(v=c(mean(A),mean(B)),col=c("#9A9287",PAL[["two"]]),lwd=2.6)
gridx(pretty(range(br),5),cex=.78,line=3.2,title="held-out MAE under the original single-split protocol")
gridy(pretty(yl,4),cex=.78,line=3.0,title="of 500 random splits")
ttl("C. It is not a lucky split","500 reseeds of the original 70/30 protocol")
segments(mean(A),max(hA$counts)*1.02,mean(A),yl[2]*.90,col="#9A9287",lwd=1,lty=3)
segments(mean(B),max(hB$counts)*1.02,mean(B),yl[2]*.74,col=PAL[["two"]],lwd=1,lty=3)
text(mean(A)-.008,yl[2]*.955,sprintf("fixed 120 d  %.3f",mean(A)),cex=.78,col="#6E675E",font=2,adj=1)
text(mean(B)+.008,yl[2]*.795,sprintf("zone-aware LGP  %.3f",mean(B)),cex=.78,col=PAL[["two"]],font=2,adj=0)
text(max(br)*.995,yl[2]*.55,"the LGP arm beats\nthe fixed cycle in\nonly 10% of the\n500 splits",
     cex=.82,col=INK,font=2,adj=1)
suptitle("Used as the crop cycle, a zone-aware LGP loses to a fixed 120-day cycle",
 c("Leave-one-out MAE 0.684 vs 0.601 t/ha, and Spearman 0.52 vs 0.72. The paired bootstrap CI touches zero, but the direction is consistent.",
   "The gain that IS real comes from a per-zone Ym on the fixed cycle (rank 0.72 to 0.83) - a ceiling correction, not a cycle-length correction."))
dev.off(); cat("ok\n")
