import argparse
import os
import sys
import pandas as pd
import matplotlib.pylab as plt
import numpy as np
from math import pi, sin, cos
from PyPDF2 import PdfFileMerger
from fpdf import FPDF

pd.options.mode.chained_assignment = None

grav_accel = 9.80665
m_to_yards = 1.09361
mph_to_mpersec = 0.44704


class Projectile:

    def __init__(self, angle, velocity):
        self.xpos = 0.0
        self.ypos = 0.0
        theta = pi * angle / 180.0
        self.xvel = mph_to_mpersec * velocity * cos(theta)
        self.yvel = mph_to_mpersec * velocity * sin(theta)
        self.maxheight = 0.0
        self.time = 0.0

    def maxHeight(self):
        self.maxheight = m_to_yards * (self.yvel ** 2) / (2 * grav_accel)
        self.getTime()
        self.getX()
        return self.maxheight, self.xpos

    def getTime(self):
        self.time = self.yvel / grav_accel

    def getX(self):
        # position along the carry distance where the max height is
        self.xpos = self.xvel * self.time * m_to_yards


def read_csv(csv_file):
    df = pd.read_csv(csv_file)

    return df


def parse_arguments():
    # create parser
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Plot the dispersion of shots from a flightscope CSV')

    # add arguments to the parser
    parser.add_argument("--csvfile", type=str, nargs='?', default='golfuture_session.csv', dest='csv_file',
                        help="Input file for the input to the flightscope data")

    # parse the arguments
    args = parser.parse_args()
    return args


def merge_pdfs(pdfs, player_name):
    merger = PdfFileMerger()

    for pdf in pdfs:
        merger.append(pdf)

    merger.write(f"results-{player_name}.pdf")
    merger.close()

    for pdf in pdfs:
        os.remove(pdf)

def create_table_values(params_list, newfilt):

    data = []

    for params in params_list:
        tmp = []

        tmp.append(params)
        tmp.append(newfilt[params].count())
        tmp.append(newfilt[params].mean())
        tmp.append(newfilt[params].median())
        tmp.append(newfilt[params].max())
        tmp.append(newfilt[params].min())
        tmp.append(newfilt[params].quantile(0.9))

        data.append(tmp)

    return data

def main():
    pd.options.display.float_format = '{:.lf}'.format

    args = parse_arguments()

    if not os.path.isfile(args.csv_file):
        print(f"Unable to find the file {args.csv_file}")
        sys.exit(1)

    # read in the file to a CSV file
    df = read_csv(args.csv_file)

    player_list = df.Player.unique()
    club_list = df.Club.unique()
    for player_name in player_list:
        pdf_list = []

        for club in club_list:

            newdf = df[(df.Player == player_name) & (df.Club == club)]

            # plot the carry and the lateral spread
            if newdf.size > 0:
                height_list = []
                xpos_list = []
                ypos_list = []

                newdf['Distance'] = np.sqrt(np.square(newdf.CarryDistance) - np.square(newdf.LateralDistance))
                for index, row in newdf.iterrows():
                    # find the max height location
                    # BallSpeed - velocity in MPH, LaunchV - angle
                    proj = Projectile(row["LaunchV"], row["BallSpeed"])
                    height, xpos = proj.maxHeight()
                    height_list.append(height)

                    # find the absolute x and y values for the max height
                    # start point is 0, 0
                    # total distance between the start and end is carrydistance
                    # have distance to the new point, dt from above
                    # need to find xt and yt
                    # the ratio of distances is t = d_t/d
                    # then xt = (1-t)*x0 + t*x1
                    # yt = (1-t)*y0 + t*y1
                    if row["CarryDistance"] > 0:
                        t = xpos / row["CarryDistance"]
                    else:
                        t = 0

                    xt = t * row["Distance"]
                    xpos_list.append(xt)

                    yt = t * row["LateralDistance"]
                    ypos_list.append(yt)

                newdf['Height'] = height_list
                newdf['XHeight'] = xpos_list
                newdf['YHeight'] = ypos_list

                newfilt = newdf.filter(['CarryDistance', 'LateralDistance', 'Height', 'Distance', 'XHeight', 'YHeight', 'TotalDistance', 'ClubSpeed', 'BallSpeed', 'SmashFactor', 'TotalSpin'],
                                       axis=1)

                collabel = ("Param", "Count", "Mean", "Median", "Max", "Min", "90th Perecent")
                params_list = ['CarryDistance', 'TotalDistance', 'ClubSpeed', 'BallSpeed', 'SmashFactor', 'TotalSpin']

                data = create_table_values(params_list, newfilt)

                maxlat = newfilt.LateralDistance.max()
                minlat = newfilt.LateralDistance.min()

                maxheight = newfilt.Height.max()

                fig = plt.figure()

                ax = plt.axes(projection='3d')
                for index, row in newdf.iterrows():
                    ylist = [0.0, row['XHeight'], row['Distance']]
                    xlist = [0.0, row['YHeight'], row['LateralDistance']]
                    zlist = [0.0, row['Height'], 0.0]
                    ax.plot3D(xlist, ylist, zlist, 'orange')

                ax.set_ylim3d(0, data[0][4] * 1.05)
                ax.set_zlim3d(0, maxheight * 1.05)

                ax.set_xlabel("Lateral Distance [yds]")
                ax.set_ylabel("Distance [yds]")
                ax.set_zlabel("Height [yds]")

                if abs(maxlat) > abs(minlat):
                    # use the max lat for the axis
                    ax.set_xlim3d(-abs(maxlat) * 1.05, abs(maxlat) * 1.05)
                else:
                    # use the min lat for the axis
                    ax.set_xlim3d(-abs(minlat) * 1.05, abs(minlat) * 1.05)

                plt.title(club)
                plt.savefig(f'{player_name}-{club}.pdf', format='pdf')
                pdf_list.append(f'{player_name}-{club}.pdf')

                plt.close()

                fig2, ax2 = plt.subplots()

                fig2.patch.set_visible(False)
                ax2.axis('off')
                ax2.axis('tight')

                plt.title(club)

                the_table = ax2.table(cellText=data, colLabels=collabel, loc='center')
                plt.savefig(f'{player_name}-{club}-sum.pdf', format='pdf')
                pdf_list.append(f'{player_name}-{club}-sum.pdf')

                plt.close()


        merge_pdfs(pdf_list, player_name)


if __name__ == "__main__":
    main()
