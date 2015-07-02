from get_database import get_section_db
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

class plot_clusters:
    def __init__(self):
        self.data = []
        self.filename = "";

    def read_data(self, filename):
        f = open(filename);
        data = []
        label = "";
        color = -1;
        sectiondb = get_section_db()
        for line in f:
            if ':' in line:
                label = line[:-1]
                color = color + 1;
            elif line.strip():
                line = line.strip()
                find_section = sectiondb.find({'_id' : line})
                if find_section.count() == 0:
                    print "section not found"
                    continue;
                section = {'label' : label, 'id' : line, 'color' : color, 'section' : find_section[0]}
                self.data.append(section)
        return self.data

    def find_in_dict(self, data, key, second_key = None):
        if key not in data:
            return False
        elif data[key] == None:
            return False
        if second_key != None:
            return self.find_in_dict(data[key], second_key)
        return True;

    def features(self):
        for i in range(len(self.data)-1,-1,-1):
            if not self.find_in_dict(self.data[i]['section'], 'section_start_point', 'coordinates'):
                self.data.pop(i)
                continue
            if not self.find_in_dict(self.data[i]['section'], 'section_end_point', 'coordinates'):
                self.data.pop(i)
                continue
            start = self.data[i]['section']['section_start_point']['coordinates']
            end = self.data[i]['section']['section_end_point']['coordinates']
            self.data[i]['startpoint'] = start
            self.data[i]['endpoint'] = end

    def calculate(self):
        print

    def graph(self):
        x = []
        y = []
        c = []
        for i in range(len(self.data)):
            xavg = (float(self.data[i]['startpoint'][0]) + float(self.data[i]['endpoint'][0]))/2.0
            yavg = (float(self.data[i]['startpoint'][1]) + float(self.data[i]['endpoint'][1]))/2.0
            x.append(xavg);
            y.append(yavg);
            #color = float(self.data[i]['color'])/len(self.data)
            #c.append(matplotlib.color.Colormap(color))
        print x
        print y
        plt.plot(x,y, 'bo')
        plt.savefig('plt.png');

if __name__ == "__main__":
    cluster = plot_clusters()
    #cluster.read_data("modified_ground_truths")
    #cluster.features()
    #cluster.graph()
